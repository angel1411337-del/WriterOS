"""
Unit tests for ProfilerAgent.

Tests entity extraction, similarity search, graph generation, and family tree construction.
"""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from writeros.agents.profiler import ProfilerAgent, WorldExtractionSchema, CharacterProfile
from writeros.schema import Entity, Relationship, EntityType, RelationType


@pytest.mark.unit
class TestProfilerAgent:
    """Test suite for ProfilerAgent."""

    @pytest.fixture(autouse=True)
    def mock_profiler_engine(self, test_engine, mocker):
        """
        Mock the ProfilerAgent's engine to use test database.
        This ensures ProfilerAgent queries run against test DB, not production.
        """
        mocker.patch("writeros.agents.profiler.engine", test_engine)

    @pytest.fixture
    def profiler(self, mock_llm_client):
        """Create a ProfilerAgent instance with mocked LLM."""
        return ProfilerAgent(model_name="gpt-4")
    
    @pytest.mark.asyncio
    async def test_entity_extraction(self, profiler, mocker):
        """Test entity extraction from text."""
        # Mock the LLM extractor
        mock_extraction = WorldExtractionSchema(
            characters=[
                CharacterProfile(
                    name="Aria Winters",
                    role="Protagonist",
                    visual_traits=[],
                    relationships=[]
                )
            ],
            organizations=[],
            locations=[]
        )
        
        profiler.extractor = AsyncMock(return_value=mock_extraction)
        
        text = "Aria Winters stood at the edge of the cliff."
        result = await profiler.run(text, "", "Test Chapter")

        assert result is not None
        assert "Aria Winters" in str(result)
    
    @pytest.mark.asyncio
    async def test_find_similar_entities(self, profiler, db_session, sample_entities, mocker):
        """Test semantic search for similar entities."""
        # Add entities to database
        for entity in sample_entities:
            db_session.add(entity)
        db_session.commit()

        # Mock embedding service
        mock_embed = mocker.patch("writeros.agents.profiler.get_embedding_service")
        mock_embed.return_value.embed_query.return_value = [0.1] * 1536

        result = await profiler.find_similar_entities("brave warrior", limit=2)

        assert result is not None
        assert isinstance(result, str)
    
    @pytest.mark.asyncio
    async def test_generate_graph_data(self, profiler, db_session, sample_entities, sample_relationships):
        """Test graph data generation."""
        vault_id = sample_entities[0].vault_id
        
        # Add data to database
        for entity in sample_entities:
            db_session.add(entity)
        for rel in sample_relationships:
            db_session.add(rel)
        db_session.commit()
        
        graph_data = await profiler.generate_graph_data(
            vault_id=vault_id,
            graph_type="force",
            max_nodes=10
        )
        
        assert "nodes" in graph_data
        assert "links" in graph_data
        assert isinstance(graph_data["nodes"], list)
        assert isinstance(graph_data["links"], list)
    
    @pytest.mark.asyncio
    async def test_build_family_tree(self, profiler, db_session, sample_vault_id):
        """Test family tree construction."""
        # Create a simple family
        parent = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Parent",
            type=EntityType.CHARACTER,
            description="Parent character",
            embedding=[0.1] * 1536
        )
        child = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Child",
            type=EntityType.CHARACTER,
            description="Child character",
            embedding=[0.2] * 1536
        )
        
        db_session.add(parent)
        db_session.add(child)
        
        rel = Relationship(
            id=uuid4(),
            vault_id=sample_vault_id,
            from_entity_id=parent.id,
            to_entity_id=child.id,
            rel_type=RelationType.PARENT,
            description="Parent-child relationship",
            properties={"strength": 1.0}
        )
        db_session.add(rel)
        db_session.commit()
        
        tree = await profiler.build_family_tree(parent.id)
        
        assert tree is not None


@pytest.mark.unit
class TestProfilerAgentHelpers:
    """Test helper methods of ProfilerAgent."""
    
    @pytest.fixture
    def profiler(self):
        """Create a ProfilerAgent instance."""
        return ProfilerAgent()
    
    def test_format_nodes(self, profiler, sample_entities):
        """Test node formatting for D3.js."""
        nodes = profiler._format_nodes(sample_entities)
        
        assert isinstance(nodes, list)
        assert len(nodes) == len(sample_entities)
        
        for node in nodes:
            assert "id" in node
            assert "name" in node
            assert "type" in node
    
    def test_format_links(self, profiler, sample_relationships):
        """Test link formatting for D3.js."""
        links = profiler._format_links(sample_relationships)

        assert isinstance(links, list)
        assert len(links) == len(sample_relationships)

        for link in links:
            assert "source" in link
            assert "target" in link
            assert "type" in link
