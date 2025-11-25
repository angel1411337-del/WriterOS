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
    async def test_build_family_tree_simple(self, profiler, db_session, sample_vault_id):
        """Test family tree construction with simple parent-child relationship."""
        # Create a simple family
        parent = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Parent",
            type=EntityType.CHARACTER,
            description="Parent character",
            properties={"role": "parent"},
            embedding=[0.1] * 1536
        )
        child = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Child",
            type=EntityType.CHARACTER,
            description="Child character",
            properties={"role": "child"},
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

        # Test from parent's perspective
        tree = await profiler.build_family_tree(parent.id)

        assert tree is not None
        assert tree["total_members"] == 2
        assert tree["generation_range"]["min"] == 0
        assert tree["generation_range"]["max"] == 1
        assert 0 in tree["generations"]  # Parent at gen 0
        assert 1 in tree["generations"]  # Child at gen 1

        # Verify parent is at generation 0
        parent_members = [m for m in tree["generations"][0] if m["name"] == "Parent"]
        assert len(parent_members) == 1
        assert parent_members[0]["properties"]["role"] == "parent"

        # Verify child is at generation 1
        child_members = [m for m in tree["generations"][1] if m["name"] == "Child"]
        assert len(child_members) == 1
        assert child_members[0]["properties"]["role"] == "child"

    @pytest.mark.asyncio
    async def test_build_family_tree_multi_generation(self, profiler, db_session, sample_vault_id):
        """Test family tree with multiple generations (grandparent → parent → child)."""
        # Create multi-generation family
        grandpa = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Grandpa Stark",
            type=EntityType.CHARACTER,
            properties={"role": "elder"},
            embedding=[0.1] * 1536
        )
        father = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Ned Stark",
            type=EntityType.CHARACTER,
            properties={"role": "father"},
            embedding=[0.2] * 1536
        )
        robb = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Robb Stark",
            type=EntityType.CHARACTER,
            properties={"role": "protagonist"},
            embedding=[0.3] * 1536
        )

        db_session.add_all([grandpa, father, robb])

        # Create relationships
        rel1 = Relationship(
            id=uuid4(),
            vault_id=sample_vault_id,
            from_entity_id=grandpa.id,
            to_entity_id=father.id,
            rel_type=RelationType.PARENT
        )
        rel2 = Relationship(
            id=uuid4(),
            vault_id=sample_vault_id,
            from_entity_id=father.id,
            to_entity_id=robb.id,
            rel_type=RelationType.PARENT
        )
        db_session.add_all([rel1, rel2])
        db_session.commit()

        # Test from Robb's perspective (middle of tree)
        tree = await profiler.build_family_tree(robb.id)

        assert tree["total_members"] == 3
        assert tree["generation_range"]["min"] == -2  # Grandpa
        assert tree["generation_range"]["max"] == 0   # Robb

        # Verify generations
        assert -2 in tree["generations"]  # Grandpa
        assert -1 in tree["generations"]  # Father
        assert 0 in tree["generations"]   # Robb

        assert tree["generations"][-2][0]["name"] == "Grandpa Stark"
        assert tree["generations"][-1][0]["name"] == "Ned Stark"
        assert tree["generations"][0][0]["name"] == "Robb Stark"

    @pytest.mark.asyncio
    async def test_build_family_tree_with_siblings(self, profiler, db_session, sample_vault_id):
        """Test family tree with sibling relationships."""
        # Create siblings
        robb = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Robb Stark",
            type=EntityType.CHARACTER,
            properties={"role": "protagonist"},
            embedding=[0.1] * 1536
        )
        sansa = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Sansa Stark",
            type=EntityType.CHARACTER,
            properties={"role": "sibling"},
            embedding=[0.2] * 1536
        )
        arya = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Arya Stark",
            type=EntityType.CHARACTER,
            properties={"role": "sibling"},
            embedding=[0.3] * 1536
        )

        db_session.add_all([robb, sansa, arya])

        # Create sibling relationships
        rel1 = Relationship(
            id=uuid4(),
            vault_id=sample_vault_id,
            from_entity_id=robb.id,
            to_entity_id=sansa.id,
            rel_type=RelationType.SIBLING
        )
        rel2 = Relationship(
            id=uuid4(),
            vault_id=sample_vault_id,
            from_entity_id=sansa.id,
            to_entity_id=arya.id,
            rel_type=RelationType.SIBLING
        )
        db_session.add_all([rel1, rel2])
        db_session.commit()

        # Test from Robb's perspective
        tree = await profiler.build_family_tree(robb.id)

        assert tree["total_members"] == 3
        assert tree["generation_range"]["min"] == 0
        assert tree["generation_range"]["max"] == 0

        # All siblings should be at generation 0
        gen_0_members = tree["generations"][0]
        assert len(gen_0_members) == 3
        names = {m["name"] for m in gen_0_members}
        assert names == {"Robb Stark", "Sansa Stark", "Arya Stark"}

    @pytest.mark.asyncio
    async def test_build_family_tree_with_child_relationship(self, profiler, db_session, sample_vault_id):
        """Test CHILD relationship (inverse of PARENT)."""
        # Create parent and child
        child = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Jon Snow",
            type=EntityType.CHARACTER,
            properties={"role": "child"},
            embedding=[0.1] * 1536
        )
        parent = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Ned Stark",
            type=EntityType.CHARACTER,
            properties={"role": "parent"},
            embedding=[0.2] * 1536
        )

        db_session.add_all([child, parent])

        # CHILD relationship: from_entity (child) → to_entity (parent)
        rel = Relationship(
            id=uuid4(),
            vault_id=sample_vault_id,
            from_entity_id=child.id,
            to_entity_id=parent.id,
            rel_type=RelationType.CHILD
        )
        db_session.add(rel)
        db_session.commit()

        # Test from child's perspective
        tree = await profiler.build_family_tree(child.id)

        assert tree["total_members"] == 2
        assert 0 in tree["generations"]   # Child
        assert -1 in tree["generations"]  # Parent (one generation up)

        assert tree["generations"][0][0]["name"] == "Jon Snow"
        assert tree["generations"][-1][0]["name"] == "Ned Stark"

    @pytest.mark.asyncio
    async def test_build_family_tree_empty(self, profiler, db_session, sample_vault_id):
        """Test family tree for entity with no relationships."""
        # Create isolated entity
        lonely = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Lonely Character",
            type=EntityType.CHARACTER,
            properties={},
            embedding=[0.1] * 1536
        )
        db_session.add(lonely)
        db_session.commit()

        tree = await profiler.build_family_tree(lonely.id)

        assert tree["total_members"] == 1
        assert tree["generation_range"]["min"] == 0
        assert tree["generation_range"]["max"] == 0
        assert len(tree["generations"][0]) == 1
        assert tree["generations"][0][0]["name"] == "Lonely Character"

    @pytest.mark.asyncio
    async def test_build_family_tree_nonexistent_entity(self, profiler, db_session):
        """Test family tree for nonexistent entity."""
        fake_id = uuid4()

        tree = await profiler.build_family_tree(fake_id)

        assert tree["total_members"] == 0
        assert tree["generation_range"]["min"] == 0
        assert tree["generation_range"]["max"] == 0
        assert tree["generations"] == {}


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
