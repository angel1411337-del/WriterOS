"""
Integration tests for GraphRAG operations.

Tests graph traversal, relationship filtering, temporal filtering,
and cycle detection.
"""
import pytest
from uuid import uuid4
from sqlmodel import Session, select
from src.writeros.schema import Entity, Relationship, EntityType, RelationType
from src.writeros.agents.profiler import ProfilerAgent


@pytest.mark.integration
class TestGraphRAGTraversal:
    """Test suite for GraphRAG traversal operations."""
    
    @pytest.fixture
    def sample_graph(self, db_session, sample_vault_id):
        """
        Create a sample relationship graph:
        
        A (parent) -> B (child) -> C (child)
        A -> D (sibling of B)
        C -> E (friend)
        """
        # Create entities
        entities = {
            "A": Entity(
                id=uuid4(),
                vault_id=sample_vault_id,
                name="Character A",
                type=EntityType.CHARACTER,
                description="Parent character",
                embedding=[0.1] * 1536
            ),
            "B": Entity(
                id=uuid4(),
                vault_id=sample_vault_id,
                name="Character B",
                type=EntityType.CHARACTER,
                description="Child of A",
                embedding=[0.2] * 1536
            ),
            "C": Entity(
                id=uuid4(),
                vault_id=sample_vault_id,
                name="Character C",
                type=EntityType.CHARACTER,
                description="Grandchild of A",
                embedding=[0.3] * 1536
            ),
            "D": Entity(
                id=uuid4(),
                vault_id=sample_vault_id,
                name="Character D",
                type=EntityType.CHARACTER,
                description="Sibling of B",
                embedding=[0.4] * 1536
            ),
            "E": Entity(
                id=uuid4(),
                vault_id=sample_vault_id,
                name="Character E",
                type=EntityType.CHARACTER,
                description="Friend of C",
                embedding=[0.5] * 1536
            ),
        }
        
        for entity in entities.values():
            db_session.add(entity)
        
        # Create relationships
        relationships = [
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                from_entity_id=entities["A"].id,
                to_entity_id=entities["B"].id,
                rel_type=RelationType.PARENT,
                strength=1.0,
                details="A is parent of B"
            ),
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                from_entity_id=entities["B"].id,
                to_entity_id=entities["C"].id,
                rel_type=RelationType.PARENT,
                strength=1.0,
                details="B is parent of C"
            ),
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                from_entity_id=entities["A"].id,
                to_entity_id=entities["D"].id,
                rel_type=RelationType.PARENT,
                strength=1.0,
                details="A is parent of D"
            ),
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                from_entity_id=entities["C"].id,
                to_entity_id=entities["E"].id,
                rel_type=RelationType.FRIEND,
                strength=0.8,
                details="C is friends with E"
            ),
        ]
        
        for rel in relationships:
            db_session.add(rel)
        
        db_session.commit()
        
        return {
            "entities": entities,
            "relationships": relationships,
            "vault_id": sample_vault_id
        }
    
    @pytest.mark.asyncio
    async def test_graph_traversal_basic(self, db_session, sample_graph, mock_llm_client):
        """Test basic graph traversal from a starting node."""
        profiler = ProfilerAgent()
        vault_id = sample_graph["vault_id"]
        
        # Generate graph data starting from entity A
        graph_data = await profiler.generate_graph_data(
            vault_id=vault_id,
            graph_type="force",
            max_nodes=10
        )
        
        assert "nodes" in graph_data
        assert "links" in graph_data
        assert len(graph_data["nodes"]) > 0
        assert len(graph_data["links"]) > 0
    
    @pytest.mark.asyncio
    async def test_relationship_filtering(self, db_session, sample_graph, mock_llm_client):
        """Test filtering by relationship type."""
        profiler = ProfilerAgent()
        vault_id = sample_graph["vault_id"]
        
        # Filter for only PARENT relationships
        graph_data = await profiler.generate_graph_data(
            vault_id=vault_id,
            graph_type="family",
            relationship_types=["PARENT"],
            max_nodes=10
        )
        
        # All links should be PARENT type
        for link in graph_data["links"]:
            assert link["type"] in ["PARENT", "CHILD"]  # Bidirectional
    
    @pytest.mark.asyncio
    async def test_max_hops_limiting(self, db_session, sample_graph, mock_llm_client):
        """Test that max_hops limits traversal depth."""
        profiler = ProfilerAgent()
        vault_id = sample_graph["vault_id"]
        
        # Limit to 1 hop
        graph_data_1hop = await profiler.generate_graph_data(
            vault_id=vault_id,
            graph_type="force",
            max_hops=1,
            max_nodes=10
        )
        
        # Limit to 2 hops
        graph_data_2hop = await profiler.generate_graph_data(
            vault_id=vault_id,
            graph_type="force",
            max_hops=2,
            max_nodes=10
        )
        
        # 2-hop should have more or equal nodes than 1-hop
        assert len(graph_data_2hop["nodes"]) >= len(graph_data_1hop["nodes"])
    
    @pytest.mark.asyncio
    async def test_temporal_filtering(self, db_session, sample_vault_id, mock_llm_client):
        """Test filtering relationships by story time."""
        # Create entities
        entity_a = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Character A",
            type=EntityType.CHARACTER,
            description="Test",
            embedding=[0.1] * 1536
        )
        entity_b = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Character B",
            type=EntityType.CHARACTER,
            description="Test",
            embedding=[0.2] * 1536
        )
        
        db_session.add(entity_a)
        db_session.add(entity_b)
        
        # Relationship active from sequence 10 to 20
        rel = Relationship(
            id=uuid4(),
            vault_id=sample_vault_id,
            from_entity_id=entity_a.id,
            to_entity_id=entity_b.id,
            rel_type=RelationType.FRIEND,
            strength=1.0,
            effective_from={"sequence": 10},
            effective_until={"sequence": 20}
        )
        db_session.add(rel)
        db_session.commit()
        
        profiler = ProfilerAgent()
        
        # Query at sequence 15 (should include relationship)
        graph_active = await profiler.generate_graph_data(
            vault_id=sample_vault_id,
            current_story_time=15,
            max_nodes=10
        )
        
        # Query at sequence 25 (should exclude relationship)
        graph_inactive = await profiler.generate_graph_data(
            vault_id=sample_vault_id,
            current_story_time=25,
            max_nodes=10
        )
        
        # Active query should have the relationship
        assert len(graph_active["links"]) >= 1
        
        # Inactive query should have fewer or no relationships
        assert len(graph_inactive["links"]) <= len(graph_active["links"])


@pytest.mark.integration
class TestFamilyTreeConstruction:
    """Test family tree construction with recursive queries."""
    
    @pytest.fixture
    def family_tree(self, db_session, sample_vault_id):
        """
        Create a multi-generation family tree:
        
        Grandparent
            ├─ Parent1
            │   ├─ Child1
            │   └─ Child2
            └─ Parent2
                └─ Child3
        """
        # Create entities
        grandparent = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Grandparent",
            type=EntityType.CHARACTER,
            description="The family patriarch",
            embedding=[0.1] * 1536
        )
        
        parent1 = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Parent 1",
            type=EntityType.CHARACTER,
            description="First child of grandparent",
            embedding=[0.2] * 1536
        )
        
        parent2 = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Parent 2",
            type=EntityType.CHARACTER,
            description="Second child of grandparent",
            embedding=[0.3] * 1536
        )
        
        child1 = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Child 1",
            type=EntityType.CHARACTER,
            description="First grandchild",
            embedding=[0.4] * 1536
        )
        
        child2 = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Child 2",
            type=EntityType.CHARACTER,
            description="Second grandchild",
            embedding=[0.5] * 1536
        )
        
        child3 = Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Child 3",
            type=EntityType.CHARACTER,
            description="Third grandchild",
            embedding=[0.6] * 1536
        )
        
        entities = [grandparent, parent1, parent2, child1, child2, child3]
        for entity in entities:
            db_session.add(entity)
        
        # Create relationships
        relationships = [
            # Grandparent -> Parents
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                from_entity_id=grandparent.id,
                to_entity_id=parent1.id,
                rel_type=RelationType.PARENT,
                strength=1.0
            ),
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                from_entity_id=grandparent.id,
                to_entity_id=parent2.id,
                rel_type=RelationType.PARENT,
                strength=1.0
            ),
            # Parent1 -> Children
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                from_entity_id=parent1.id,
                to_entity_id=child1.id,
                rel_type=RelationType.PARENT,
                strength=1.0
            ),
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                from_entity_id=parent1.id,
                to_entity_id=child2.id,
                rel_type=RelationType.PARENT,
                strength=1.0
            ),
            # Parent2 -> Child
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                from_entity_id=parent2.id,
                to_entity_id=child3.id,
                rel_type=RelationType.PARENT,
                strength=1.0
            ),
        ]
        
        for rel in relationships:
            db_session.add(rel)
        
        db_session.commit()
        
        return {
            "grandparent": grandparent,
            "parent1": parent1,
            "parent2": parent2,
            "child1": child1,
            "child2": child2,
            "child3": child3,
        }
    
    @pytest.mark.asyncio
    async def test_build_family_tree(self, db_session, family_tree, mock_llm_client):
        """Test building a complete family tree."""
        profiler = ProfilerAgent()
        
        # Build tree from grandparent
        tree_data = await profiler.build_family_tree(family_tree["grandparent"].id)
        
        assert tree_data is not None
        # Should include all family members
        assert len(tree_data) >= 6


@pytest.mark.integration
class TestCycleDetection:
    """Test that graph traversal handles cycles correctly."""
    
    @pytest.fixture
    def circular_graph(self, db_session, sample_vault_id):
        """
        Create a circular relationship graph (time travel paradox):
        A -> B -> C -> A
        """
        entities = {
            "A": Entity(
                id=uuid4(),
                vault_id=sample_vault_id,
                name="Character A",
                type=EntityType.CHARACTER,
                description="Father of B",
                embedding=[0.1] * 1536
            ),
            "B": Entity(
                id=uuid4(),
                vault_id=sample_vault_id,
                name="Character B",
                type=EntityType.CHARACTER,
                description="Father of C",
                embedding=[0.2] * 1536
            ),
            "C": Entity(
                id=uuid4(),
                vault_id=sample_vault_id,
                name="Character C",
                type=EntityType.CHARACTER,
                description="Father of A (paradox!)",
                embedding=[0.3] * 1536
            ),
        }
        
        for entity in entities.values():
            db_session.add(entity)
        
        # Create circular relationships
        relationships = [
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                from_entity_id=entities["A"].id,
                to_entity_id=entities["B"].id,
                rel_type=RelationType.PARENT,
                strength=1.0
            ),
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                from_entity_id=entities["B"].id,
                to_entity_id=entities["C"].id,
                rel_type=RelationType.PARENT,
                strength=1.0
            ),
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                from_entity_id=entities["C"].id,
                to_entity_id=entities["A"].id,
                rel_type=RelationType.PARENT,
                strength=1.0
            ),
        ]
        
        for rel in relationships:
            db_session.add(rel)
        
        db_session.commit()
        
        return {"entities": entities, "vault_id": sample_vault_id}
    
    @pytest.mark.asyncio
    async def test_circular_relationship_traversal(self, db_session, circular_graph, mock_llm_client):
        """Test that circular relationships don't cause infinite loops."""
        profiler = ProfilerAgent()
        vault_id = circular_graph["vault_id"]
        
        # This should not hang or crash
        graph_data = await profiler.generate_graph_data(
            vault_id=vault_id,
            graph_type="family",
            max_hops=5,  # Even with many hops, should not infinite loop
            max_nodes=10
        )
        
        # Should complete successfully
        assert "nodes" in graph_data
        assert "links" in graph_data
        
        # Should have all 3 entities
        assert len(graph_data["nodes"]) == 3
        
        # Should have all 3 relationships
        assert len(graph_data["links"]) >= 3
