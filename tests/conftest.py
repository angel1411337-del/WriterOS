"""
Pytest configuration and shared fixtures for WriterOS tests.
"""
import pytest
from pathlib import Path
from uuid import uuid4
from sqlmodel import create_engine, SQLModel, Session

# Test database URL (separate from production)
TEST_DATABASE_URL = "postgresql://writer:password@localhost:5432/writeros_test"


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def db_session(test_engine):
    """Create a database session for a test."""
    with Session(test_engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def sample_vault_id():
    """Generate a test vault ID."""
    return uuid4()


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def manuscripts_dir(fixtures_dir):
    """Path to sample manuscript files."""
    return fixtures_dir / "manuscripts"
