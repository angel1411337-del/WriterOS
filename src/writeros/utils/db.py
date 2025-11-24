from writeros.core.logging import get_logger
from sqlmodel import create_engine, SQLModel, Session, text
from dotenv import load_dotenv
import time
import os

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__)

# Connection string - MUST be set via environment variable
# No default provided for security - prevents accidental use of hardcoded credentials
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    error_msg = (
        "DATABASE_URL environment variable is not set. "
        "Please set it to your PostgreSQL connection string. "
        "Example: postgresql://user:password@host:port/database"
    )
    logger.critical("database_url_not_set")
    raise EnvironmentError(error_msg)

# Connection Pool Configuration
# These can be customized via environment variables for performance tuning
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "40"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))
POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"

# Create the Engine with High-Performance Connection Pooling
# Benefits:
# - pool_size: Maintains N persistent connections (reuse instead of create/destroy)
# - max_overflow: Allows temporary connections beyond pool during traffic spikes
# - pool_pre_ping: Tests connections before use (prevents stale connection errors)
# - pool_recycle: Recycles connections after N seconds (prevents idle timeouts)
# Expected improvement: 5x-10x throughput, eliminates connection overhead
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_pre_ping=POOL_PRE_PING,
    pool_recycle=POOL_RECYCLE,
)

logger.info(
    "database_engine_configured",
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=POOL_PRE_PING,
    total_connections=POOL_SIZE + MAX_OVERFLOW,
)

def init_db():
    """
    Initializes the database with tables and high-performance vector indexes.
    """
    max_retries = 5
    for i in range(max_retries):
        try:
            logger.info("connecting_to_database", attempt=i+1)

            # 1. Enable Vector Extension
            with Session(engine) as session:
                session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
                session.commit()

            # 2. Register Tables
            from writeros import schema

            # 3. Create Tables
            SQLModel.metadata.create_all(engine)

            # 4. Create High-Performance Vector Indexes
            # HNSW (Hierarchical Navigable Small World) indexes provide 100x-1000x speedup
            # for nearest-neighbor vector searches compared to sequential scans
            logger.info("creating_vector_indexes")
            with Session(engine) as session:
                # Entities table - semantic entity search
                session.exec(text("""
                    CREATE INDEX IF NOT EXISTS entities_embedding_hnsw_idx
                    ON entities USING hnsw (embedding vector_cosine_ops)
                """))

                # Documents table - semantic document search
                session.exec(text("""
                    CREATE INDEX IF NOT EXISTS documents_embedding_hnsw_idx
                    ON documents USING hnsw (embedding vector_cosine_ops)
                """))

                # Facts table - semantic fact search
                session.exec(text("""
                    CREATE INDEX IF NOT EXISTS facts_embedding_hnsw_idx
                    ON facts USING hnsw (embedding vector_cosine_ops)
                """))

                session.commit()
                logger.info("vector_indexes_created", status="success")

            logger.info("database_initialized", status="success")
            return
        except Exception as e:
            logger.error("database_connection_failed", error=str(e), attempt=i+1)
            if i < max_retries - 1:
                logger.info("retrying_connection", delay=2)
                time.sleep(2)
            else:
                logger.critical("initialization_failed")

def get_session():
    """FastAPI Dependency"""
    with Session(engine) as session:
        yield session

def get_or_create_vault_id(vault_path: str) -> "UUID":
    """
    Gets the vault ID from .writeros/vault_id or creates a new one.
    """
    from pathlib import Path
    from uuid import uuid4, UUID
    
    path_obj = Path(vault_path)
    config_dir = path_obj / ".writeros"
    config_dir.mkdir(exist_ok=True)
    
    id_file = config_dir / "vault_id"
    
    if id_file.exists():
        try:
            return UUID(id_file.read_text().strip())
        except ValueError:
            logger.warning("invalid_vault_id_file", path=str(id_file))
            
    new_id = uuid4()
    id_file.write_text(str(new_id))
    logger.info("created_new_vault_id", id=str(new_id))
    return new_id

if __name__ == "__main__":
    init_db()