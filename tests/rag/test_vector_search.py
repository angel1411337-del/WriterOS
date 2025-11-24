"""
Integration tests for Vector Search operations using pgvector.

Tests cosine similarity, L2 distance, filtering, and ranking.
"""
import pytest
from uuid import uuid4
from sqlmodel import Session, select
from writeros.schema import Entity, Document, Fact, EntityType, FactType


@pytest.mark.integration
class TestVectorSearch:
    """Test suite for vector search operations."""
    
    @pytest.fixture
    def sample_vault_id(self):
        """Generate a test vault ID."""
        return uuid4()
    
    @pytest.fixture
    def populated_db(self, db_session, sample_vault_id):
        """Populate database with test entities."""
        entities = [
            Entity(
                id=uuid4(),
                vault_id=sample_vault_id,
                name="Warrior Character",
                type=EntityType.CHARACTER,
                description="A brave warrior who fights for justice",
                embedding=[0.9, 0.8, 0.7] + [0.0] * 1533  # Pad to 1536
            ),
            Entity(
                id=uuid4(),
                vault_id=sample_vault_id,
                name="Coward Character",
                type=EntityType.CHARACTER,
                description="A cowardly merchant who avoids conflict",
                embedding=[0.1, 0.2, 0.1] + [0.0] * 1533
            ),
            Entity(
                id=uuid4(),
                vault_id=sample_vault_id,
                name="Dark Forest",
                type=EntityType.LOCATION,
                description="A mysterious forest filled with danger",
                embedding=[0.5, 0.5, 0.9] + [0.0] * 1533
            ),
        ]
        
        for entity in entities:
            db_session.add(entity)
        db_session.commit()
        
        return {"entities": entities, "vault_id": sample_vault_id}
    
    def test_cosine_similarity_search(self, db_session, populated_db):
        """Test cosine similarity search for entities."""
        vault_id = populated_db["vault_id"]
        
        # Query vector similar to "warrior"
        query_embedding = [0.85, 0.75, 0.65] + [0.0] * 1533
        
        # Search using cosine distance
        results = db_session.exec(
            select(Entity)
            .where(Entity.vault_id == vault_id)
            .order_by(Entity.embedding.cosine_distance(query_embedding))
            .limit(2)
        ).all()
        
        assert len(results) >= 1
        # First result should be the warrior (most similar)
        assert "warrior" in results[0].name.lower() or "brave" in results[0].description.lower()
    
    def test_l2_distance_search(self, db_session, populated_db):
        """Test L2 (Euclidean) distance search."""
        vault_id = populated_db["vault_id"]
        
        # Query vector
        query_embedding = [0.9, 0.8, 0.7] + [0.0] * 1533
        
        results = db_session.exec(
            select(Entity)
            .where(Entity.vault_id == vault_id)
            .order_by(Entity.embedding.l2_distance(query_embedding))
            .limit(2)
        ).all()
        
        assert len(results) >= 1
        # Should return warrior first (exact match)
        assert results[0].name == "Warrior Character"
    
    def test_filter_by_vault_id(self, db_session, populated_db):
        """Test that search correctly filters by vault_id."""
        vault_id = populated_db["vault_id"]
        different_vault_id = uuid4()
        
        # Add entity to different vault
        other_entity = Entity(
            id=uuid4(),
            vault_id=different_vault_id,
            name="Other Vault Entity",
            type=EntityType.CHARACTER,
            description="Should not appear in results",
            embedding=[0.9, 0.8, 0.7] + [0.0] * 1533
        )
        db_session.add(other_entity)
        db_session.commit()
        
        # Search only in original vault
        query_embedding = [0.9, 0.8, 0.7] + [0.0] * 1533
        results = db_session.exec(
            select(Entity)
            .where(Entity.vault_id == vault_id)
            .order_by(Entity.embedding.cosine_distance(query_embedding))
        ).all()
        
        # Should not include entity from other vault
        assert all(e.vault_id == vault_id for e in results)
        assert not any(e.name == "Other Vault Entity" for e in results)
    
    def test_result_ranking(self, db_session, populated_db):
        """Test that results are correctly ranked by similarity."""
        vault_id = populated_db["vault_id"]
        
        # Query for "brave warrior"
        query_embedding = [0.9, 0.8, 0.7] + [0.0] * 1533
        
        results = db_session.exec(
            select(Entity)
            .where(Entity.vault_id == vault_id)
            .order_by(Entity.embedding.cosine_distance(query_embedding))
        ).all()
        
        # Warrior should be first (exact match with query vector)
        assert results[0].name == "Warrior Character"
        # Verify all 3 entities are returned
        assert len(results) == 3
    
    def test_empty_result_handling(self, db_session):
        """Test search with no results."""
        empty_vault_id = uuid4()
        query_embedding = [0.5] * 1536
        
        results = db_session.exec(
            select(Entity)
            .where(Entity.vault_id == empty_vault_id)
            .order_by(Entity.embedding.cosine_distance(query_embedding))
        ).all()
        
        assert results == []
    
    def test_limit_parameter(self, db_session, populated_db):
        """Test that limit parameter works correctly."""
        vault_id = populated_db["vault_id"]
        query_embedding = [0.5] * 1536
        
        results = db_session.exec(
            select(Entity)
            .where(Entity.vault_id == vault_id)
            .order_by(Entity.embedding.cosine_distance(query_embedding))
            .limit(2)
        ).all()
        
        assert len(results) <= 2


@pytest.mark.integration
class TestDocumentVectorSearch:
    """Test vector search on Document table."""
    
    @pytest.fixture
    def populated_docs(self, db_session, sample_vault_id):
        """Populate database with test documents."""
        docs = [
            Document(
                id=uuid4(),
                vault_id=sample_vault_id,
                title="Battle Scene",
                content="The warrior charged into battle with his sword raised high.",
                doc_type="manuscript",
                embedding=[0.9, 0.8, 0.7] + [0.0] * 1533
            ),
            Document(
                id=uuid4(),
                vault_id=sample_vault_id,
                title="Romance Scene",
                content="They gazed into each other's eyes under the moonlight.",
                doc_type="manuscript",
                embedding=[0.1, 0.2, 0.3] + [0.0] * 1533
            ),
        ]
        
        for doc in docs:
            db_session.add(doc)
        db_session.commit()
        
        return {"docs": docs, "vault_id": sample_vault_id}
    
    def test_document_search(self, db_session, populated_docs):
        """Test semantic search over documents."""
        vault_id = populated_docs["vault_id"]
        
        # Query for battle-related content
        query_embedding = [0.85, 0.75, 0.65] + [0.0] * 1533
        
        results = db_session.exec(
            select(Document)
            .where(Document.vault_id == vault_id)
            .order_by(Document.embedding.cosine_distance(query_embedding))
            .limit(1)
        ).all()
        
        assert len(results) == 1
        assert "Battle" in results[0].title


@pytest.mark.integration
class TestFactVectorSearch:
    """Test vector search on Fact table."""
    
    @pytest.fixture
    def populated_facts(self, db_session, sample_vault_id):
        """Populate database with test facts."""
        entity_id = uuid4()
        
        # Create entity first
        entity = Entity(
            id=entity_id,
            vault_id=sample_vault_id,
            name="Test Character",
            type=EntityType.CHARACTER,
            description="Test",
            embedding=[0.5] * 1536
        )
        db_session.add(entity)
        
        facts = [
            Fact(
                id=uuid4(),
                entity_id=entity_id,
                fact_type=FactType.TRAIT,
                content="Brave and honorable warrior",
                embedding=[0.9, 0.8, 0.7] + [0.0] * 1533
            ),
            Fact(
                id=uuid4(),
                entity_id=entity_id,
                fact_type=FactType.FEAR,
                content="Afraid of spiders",
                embedding=[0.1, 0.2, 0.1] + [0.0] * 1533
            ),
        ]
        
        for fact in facts:
            db_session.add(fact)
        db_session.commit()
        
        return {"facts": facts, "entity_id": entity_id}
    
    def test_fact_search(self, db_session, populated_facts):
        """Test semantic search over facts."""
        # Query for personality traits
        query_embedding = [0.85, 0.75, 0.65] + [0.0] * 1533
        
        results = db_session.exec(
            select(Fact)
            .order_by(Fact.embedding.cosine_distance(query_embedding))
            .limit(1)
        ).all()
        
        assert len(results) == 1
        assert "brave" in results[0].content.lower() or "honorable" in results[0].content.lower()
