"""
End-to-end tests for the complete RAG pipeline.

Tests the full flow: Ingest → Chunk → Embed → Store → Query → Retrieve → Rank
"""
import pytest
from pathlib import Path
from uuid import uuid4
from src.writeros.utils.indexer import VaultIndexer
from src.writeros.agents.profiler import ProfilerAgent
from src.writeros.schema import Document, Entity


@pytest.mark.e2e
@pytest.mark.slow
class TestRAGPipelineE2E:
    """End-to-end tests for the complete RAG pipeline."""
    
    @pytest.fixture
    def test_vault(self, tmp_path):
        """Create a test vault with sample files."""
        vault_root = tmp_path / "test_vault"
        vault_root.mkdir()
        
        # Create directory structure
        story_bible = vault_root / "Story_Bible" / "Characters"
        story_bible.mkdir(parents=True)
        
        manuscripts = vault_root / "Manuscripts"
        manuscripts.mkdir(parents=True)
        
        # Create sample character file
        char_file = story_bible / "protagonist.md"
        char_file.write_text("""
# Aria Winters

## Description
Aria is a skilled hacker living in Neo Tokyo. She has cybernetic eyes that glow blue.

## Personality
- Brave and determined
- Distrusts authority
- Loyal to her friends

## Background
Her family was killed by The Syndicate when she was young.
""")
        
        # Create sample manuscript
        manuscript_file = manuscripts / "chapter_01.md"
        manuscript_file.write_text("""
# Chapter 1: The Heist

Aria crouched on the rooftop, her cybernetic eyes scanning the building below.
The corporate headquarters loomed like a fortress of glass and steel.

"Ready?" her partner whispered through the comm.

"Always," Aria replied, checking her equipment one last time.
""")
        
        return vault_root
    
    @pytest.mark.asyncio
    async def test_full_ingestion_pipeline(
        self,
        test_vault,
        db_session,
        mock_embedding_service
    ):
        """Test: Ingest markdown → Chunk → Embed → Store."""
        vault_id = uuid4()
        
        # Create indexer
        indexer = VaultIndexer(
            vault_path=str(test_vault),
            vault_id=vault_id
        )
        
        # Index the vault
        results = await indexer.index_vault()
        
        # Verify results
        assert results["files_processed"] >= 2
        assert results["chunks_created"] > 0
        assert len(results["errors"]) == 0
        
        # Verify documents were stored
        docs = db_session.query(Document).filter(
            Document.vault_id == vault_id
        ).all()
        
        assert len(docs) > 0
        
        # Each document should have an embedding
        for doc in docs:
            assert doc.embedding is not None
            assert len(doc.embedding) == 1536
    
    @pytest.mark.asyncio
    async def test_full_retrieval_pipeline(
        self,
        test_vault,
        db_session,
        sample_vault_id,
        mock_embedding_service
    ):
        """Test: Query → Retrieve → Rank → Return."""
        # First, populate database with test data
        doc1 = Document(
            id=uuid4(),
            vault_id=sample_vault_id,
            title="Character: Aria",
            content="Aria is a skilled hacker with cybernetic eyes.",
            doc_type="character_sheet",
            embedding=[0.9, 0.8, 0.7] + [0.0] * 1533
        )
        
        doc2 = Document(
            id=uuid4(),
            vault_id=sample_vault_id,
            title="Chapter 1",
            content="The hero fought bravely against the dragon.",
            doc_type="manuscript",
            embedding=[0.1, 0.2, 0.3] + [0.0] * 1533
        )
        
        db_session.add(doc1)
        db_session.add(doc2)
        db_session.commit()
        
        # Mock embedding for query
        mock_embedding_service.embed_query.return_value = [0.85, 0.75, 0.65] + [0.0] * 1533
        
        # Perform semantic search
        from sqlmodel import select
        query_embedding = [0.85, 0.75, 0.65] + [0.0] * 1533
        
        results = db_session.exec(
            select(Document)
            .where(Document.vault_id == sample_vault_id)
            .order_by(Document.embedding.cosine_distance(query_embedding))
            .limit(1)
        ).all()
        
        # Should retrieve the hacker document (more similar)
        assert len(results) == 1
        assert "Aria" in results[0].title or "hacker" in results[0].content
    
    @pytest.mark.asyncio
    async def test_graphrag_query_with_multi_hop(
        self,
        db_session,
        sample_vault_id,
        mock_llm_client
    ):
        """Test: GraphRAG query with multi-hop traversal."""
        # Create a chain of entities: A -> B -> C
        entity_a = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Entity A",
            type="CHARACTER",
            description="First entity",
            embedding=[0.1] * 1536
        )
        entity_b = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Entity B",
            type="CHARACTER",
            description="Second entity",
            embedding=[0.2] * 1536
        )
        entity_c = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Entity C",
            type="CHARACTER",
            description="Third entity",
            embedding=[0.3] * 1536
        )
        
        db_session.add(entity_a)
        db_session.add(entity_b)
        db_session.add(entity_c)
        
        from src.writeros.schema import Relationship, RelationType
        
        rel_ab = Relationship(
            id=uuid4(),
            vault_id=sample_vault_id,
            from_entity_id=entity_a.id,
            to_entity_id=entity_b.id,
            rel_type=RelationType.FRIEND,
            strength=1.0
        )
        rel_bc = Relationship(
            id=uuid4(),
            vault_id=sample_vault_id,
            from_entity_id=entity_b.id,
            to_entity_id=entity_c.id,
            rel_type=RelationType.FRIEND,
            strength=1.0
        )
        
        db_session.add(rel_ab)
        db_session.add(rel_bc)
        db_session.commit()
        
        # Query with 2-hop traversal
        profiler = ProfilerAgent()
        graph_data = await profiler.generate_graph_data(
            vault_id=sample_vault_id,
            max_hops=2,
            max_nodes=10
        )
        
        # Should include all 3 entities
        assert len(graph_data["nodes"]) == 3
        assert len(graph_data["links"]) >= 2


@pytest.mark.e2e
class TestRAGPipelinePerformance:
    """Performance tests for RAG pipeline."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_large_document_chunking(self, tmp_path, mock_embedding_service):
        """Test chunking performance with large documents."""
        from src.writeros.preprocessing.chunker import SemanticChunker
        
        # Create a large document (10,000 words)
        large_text = " ".join([f"Sentence number {i}." for i in range(5000)])
        
        chunker = SemanticChunker(min_chunk_size=100, max_chunk_size=400)
        
        # This should complete in reasonable time
        import time
        start = time.time()
        chunks = await chunker.chunk_document(large_text)
        elapsed = time.time() - start
        
        # Should complete in < 5 seconds (with mocked embeddings)
        assert elapsed < 5.0
        assert len(chunks) > 0
    
    @pytest.mark.asyncio
    async def test_vector_search_performance(self, db_session, sample_vault_id):
        """Test vector search performance with many entities."""
        from src.writeros.schema import Entity, EntityType
        
        # Create 100 entities
        entities = []
        for i in range(100):
            entity = Entity(
                id=uuid4(),
                vault_id=sample_vault_id,
                name=f"Entity {i}",
                type=EntityType.CHARACTER,
                description=f"Description for entity {i}",
                embedding=[i * 0.01] * 1536
            )
            entities.append(entity)
            db_session.add(entity)
        
        db_session.commit()
        
        # Perform search
        from sqlmodel import select
        import time
        
        query_embedding = [0.5] * 1536
        
        start = time.time()
        results = db_session.exec(
            select(Entity)
            .where(Entity.vault_id == sample_vault_id)
            .order_by(Entity.embedding.cosine_distance(query_embedding))
            .limit(10)
        ).all()
        elapsed = time.time() - start
        
        # Should complete quickly (< 1 second)
        assert elapsed < 1.0
        assert len(results) == 10
