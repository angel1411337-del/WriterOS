"""
Pytest configuration and shared fixtures for WriterOS tests.
"""
import pytest
import asyncio
from typing import AsyncGenerator, List
from pathlib import Path
from uuid import uuid4, UUID
from unittest.mock import MagicMock, AsyncMock
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# ============================================================================
# ⭐ DB CONFIGURATION (Updated for Docker Port 5433)
# ============================================================================
# Use 127.0.0.1 to avoid Windows IPv6 issues
# Use Port 5433 to match your running Docker container
TEST_DATABASE_URL = "postgresql://writer:password@127.0.0.1:5433/writeros_test"
TEST_ASYNC_DATABASE_URL = "postgresql+asyncpg://writer:password@127.0.0.1:5433/writeros_test"


# ============================================================================
# Event Loop Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_engine():
    """Create a synchronous test database engine (for simple tests)."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def db_session(test_engine):
    """Create a database session for a test (synchronous)."""
    with Session(test_engine) as session:
        yield session
        session.rollback()


@pytest.fixture(scope="session")
async def async_db_engine():
    """
    Create async engine for integration tests.
    Requires Docker PostgreSQL to be running.
    """
    from sqlalchemy import text
    engine = create_async_engine(TEST_ASYNC_DATABASE_URL, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
        # Enable vector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def async_db_session(async_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a new async session for each async test.
    Use this fixture for async test methods.
    """
    connection = await async_db_engine.connect()
    transaction = await connection.begin()

    session_factory = sessionmaker(
        bind=connection, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    await transaction.rollback()
    await connection.close()


# ============================================================================
# Mock Services
# ============================================================================

@pytest.fixture
def mock_embedding_service(mocker):
    """
    Mock EmbeddingService to return deterministic vectors.
    Avoids OpenAI API calls during tests.
    """
    mock = mocker.patch("writeros.utils.embeddings.EmbeddingService")
    service = MagicMock()

    # Return a fake vector (1536 dims for text-embedding-3-small)
    fake_vector = [0.1] * 1536
    service.embed_query.return_value = fake_vector
    service.embed_documents.return_value = [fake_vector, fake_vector]

    # Add async method for async compatibility
    async def mock_get_embeddings(texts):
        return [[0.1] * 1536 for _ in texts]
    service.get_embeddings = AsyncMock(side_effect=mock_get_embeddings)

    mock.return_value = service
    return service


@pytest.fixture
def mock_llm_client(mocker):
    """
    Mock LLM client to avoid API costs.
    Returns deterministic structured outputs.
    """
    mock = mocker.patch("writeros.agents.base.ChatOpenAI")
    client = MagicMock()
    
    # Mock structured output
    async def mock_ainvoke(*args, **kwargs):
        return MagicMock(content="Mocked LLM response")
    
    client.ainvoke = AsyncMock(side_effect=mock_ainvoke)
    mock.return_value = client
    return client


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_vault_id() -> UUID:
    """Generate a test vault ID."""
    return uuid4()


@pytest.fixture
def sample_entities(sample_vault_id):
    """Create sample entity data for testing."""
    from writeros.schema import Entity, EntityType
    
    return [
        Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Aria Winters",
            type=EntityType.CHARACTER,
            description="A skilled hacker navigating the neon-lit streets of Neo Tokyo",
            properties={"role": "protagonist", "age": 28},
            embedding=[0.1] * 1536
        ),
        Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="Neo Tokyo",
            type=EntityType.LOCATION,
            description="A sprawling megacity dominated by corporate skyscrapers",
            properties={"population": 50000000},
            embedding=[0.2] * 1536
        ),
        Entity(
            id=uuid4(),
            vault_id=sample_vault_id,
            name="The Syndicate",
            type=EntityType.FACTION,
            description="A powerful criminal organization controlling the underworld",
            properties={"influence": "high"},
            embedding=[0.3] * 1536
        ),
    ]


@pytest.fixture
def sample_relationships(sample_entities):
    """Create sample relationship data."""
    from writeros.schema import Relationship, RelationType
    
    return [
        Relationship(
            id=uuid4(),
            vault_id=sample_entities[0].vault_id,
            from_entity_id=sample_entities[0].id,
            to_entity_id=sample_entities[2].id,
            rel_type=RelationType.ENEMY,
            description="Aria is actively fighting against The Syndicate",
            properties={"strength": 0.9}
        ),
        Relationship(
            id=uuid4(),
            vault_id=sample_entities[0].vault_id,
            from_entity_id=sample_entities[0].id,
            to_entity_id=sample_entities[1].id,
            rel_type=RelationType.LOCATED_IN,
            description="Aria lives in Neo Tokyo",
            properties={"strength": 1.0}
        ),
    ]


@pytest.fixture
def sample_documents(sample_vault_id):
    """Create sample document data."""
    from writeros.schema import Document
    
    return [
        Document(
            id=uuid4(),
            vault_id=sample_vault_id,
            title="Chapter 1: The Heist",
            content="Aria crouched on the rooftop, her cybernetic eyes scanning the building below...",
            doc_type="manuscript",
            embedding=[0.4] * 1536,
            metadata_={"chapter": 1, "word_count": 2500}
        ),
        Document(
            id=uuid4(),
            vault_id=sample_vault_id,
            title="Character Notes: Aria",
            content="Aria is a skilled hacker with a tragic past. Her family was killed by The Syndicate...",
            doc_type="character_sheet",
            embedding=[0.5] * 1536,
            metadata_={"character": "Aria Winters"}
        ),
    ]


# ============================================================================
# File System Fixtures
# ============================================================================

@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def manuscripts_dir(fixtures_dir):
    """Path to sample manuscript files."""
    return fixtures_dir / "manuscripts"


@pytest.fixture
def sample_markdown_file(tmp_path):
    """Create a temporary markdown file for testing."""
    file_path = tmp_path / "test_chapter.md"
    file_path.write_text("""
# Chapter 1: The Beginning

The hero stood at the edge of the cliff. Below, the valley stretched endlessly.
He knew this was the moment that would change everything.

## Scene 1

The wind howled. Rain pelted his face. But he didn't move.
""")
    return file_path


# ============================================================================
# Utility Functions
# ============================================================================

def create_test_vault(tmp_path: Path, num_files: int = 3) -> Path:
    """
    Create a temporary vault structure for testing.
    
    Args:
        tmp_path: Pytest tmp_path fixture
        num_files: Number of markdown files to create
        
    Returns:
        Path to vault root
    """
    vault_root = tmp_path / "test_vault"
    vault_root.mkdir()
    
    # Create directory structure
    (vault_root / "Story_Bible" / "Characters").mkdir(parents=True)
    (vault_root / "Story_Bible" / "Locations").mkdir(parents=True)
    (vault_root / "Manuscripts").mkdir(parents=True)
    
    # Create sample files
    for i in range(num_files):
        char_file = vault_root / "Story_Bible" / "Characters" / f"character_{i}.md"
        char_file.write_text(f"# Character {i}\\n\\nThis is character {i}'s description.")
        
    return vault_root