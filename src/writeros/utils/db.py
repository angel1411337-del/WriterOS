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
    Initializes the database with tables, indexes, and default data.

    Hybrid Architecture Support:
    - LOCAL mode: Auto-creates admin user and default vault
    - SAAS mode: Only creates schema (users created via signup)

    UUID Preservation:
    - Reads existing vault UUID from filesystem (.writeros/vault_id)
    - Creates Vault record with SAME UUID to preserve entity links
    - Prevents orphaned data from alpha/beta migrations
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

                # Scenes table - semantic scene search
                session.exec(text("""
                    CREATE INDEX IF NOT EXISTS scenes_embedding_hnsw_idx
                    ON scenes USING hnsw (embedding vector_cosine_ops)
                """))

                # Events table - semantic event search
                session.exec(text("""
                    CREATE INDEX IF NOT EXISTS events_embedding_hnsw_idx
                    ON events USING hnsw (embedding vector_cosine_ops)
                """))

                # Conflicts table - semantic conflict search
                session.exec(text("""
                    CREATE INDEX IF NOT EXISTS conflicts_embedding_hnsw_idx
                    ON conflicts USING hnsw (embedding vector_cosine_ops)
                """))

                session.commit()
                logger.info("vector_indexes_created", status="success")

            # 5. Initialize Default Data (LOCAL mode only)
            mode = os.getenv("WRITEROS_MODE", "local")
            logger.info("initializing_default_data", mode=mode)

            if mode == "local":
                ensure_default_user_and_vault()
            else:
                logger.info("skipping_default_data", reason="saas_mode")

            logger.info("database_initialized", status="success", mode=mode)
            return
        except Exception as e:
            logger.error("database_connection_failed", error=str(e), attempt=i+1)
            if i < max_retries - 1:
                logger.info("retrying_connection", delay=2)
                time.sleep(2)
            else:
                logger.critical("initialization_failed")
                raise

def ensure_default_user_and_vault():
    """
    Ensures default admin user and vault exist (LOCAL mode only).

    CRITICAL: UUID Preservation Logic
    - Reads existing vault_id from filesystem if it exists
    - Creates Vault record with SAME UUID to preserve entity links
    - Only generates new UUID if no filesystem record exists

    This prevents orphaned entities from alpha/beta users who have
    data linked to the old UUID.
    """
    from uuid import uuid4
    from sqlmodel import select
    from writeros.schema import User, Vault, ConnectionType, SubscriptionTier

    with Session(engine) as session:
        # 1. Ensure Admin User Exists
        admin_email = os.getenv("WRITEROS_ADMIN_EMAIL", "admin@writeros.local")
        admin_username = os.getenv("WRITEROS_ADMIN_USERNAME", "admin")

        admin_user = session.exec(
            select(User).where(User.email == admin_email)
        ).first()

        if not admin_user:
            logger.info("creating_default_admin_user", email=admin_email)
            admin_user = User(
                email=admin_email,
                username=admin_username,
                display_name="System Administrator",
                tier=SubscriptionTier.FREE,
                auth_provider="local"
            )
            session.add(admin_user)
            session.commit()
            session.refresh(admin_user)
            logger.info("admin_user_created", user_id=str(admin_user.id))
        else:
            logger.info("admin_user_already_exists", user_id=str(admin_user.id))

        # 2. Handle Vault Migration (CRITICAL STEP)
        vault_path = os.getenv("VAULT_PATH", ".")

        # Check filesystem for existing UUID
        existing_uuid_on_disk = read_uuid_from_filesystem(vault_path)

        # Check if Vault record exists in database
        vault = None
        if existing_uuid_on_disk:
            vault = session.get(Vault, existing_uuid_on_disk)
            if vault:
                logger.info("vault_already_exists", vault_id=str(vault.id), name=vault.name)

        if not vault:
            # Create Vault using EXISTING UUID (preserves data links)
            # or generate new UUID if no filesystem record
            vault_id = existing_uuid_on_disk or uuid4()
            vault_name = os.getenv("WRITEROS_VAULT_NAME") or get_directory_name(vault_path)

            logger.info(
                "creating_default_vault",
                vault_id=str(vault_id),
                name=vault_name,
                preserved_uuid=existing_uuid_on_disk is not None
            )

            vault = Vault(
                id=vault_id,
                name=vault_name,
                owner_id=admin_user.id,
                connection_type=ConnectionType.LOCAL_OBSIDIAN,
                local_system_path=vault_path
            )
            session.add(vault)
            session.commit()
            session.refresh(vault)

            logger.info("vault_created", vault_id=str(vault.id), name=vault.name)

            # Save UUID to filesystem if it was newly generated
            if not existing_uuid_on_disk:
                write_uuid_to_filesystem(vault.id, vault_path)
        else:
            # Vault exists - ensure it has an owner
            if not vault.owner_id:
                logger.info("assigning_owner_to_existing_vault", vault_id=str(vault.id))
                vault.owner_id = admin_user.id
                session.add(vault)
                session.commit()

        logger.info(
            "default_user_and_vault_ready",
            user_id=str(admin_user.id),
            vault_id=str(vault.id),
            vault_name=vault.name
        )


def get_session():
    """FastAPI Dependency"""
    with Session(engine) as session:
        yield session

def read_uuid_from_filesystem(vault_path: str = None) -> "UUID | None":
    """
    Read existing vault UUID from filesystem if it exists.
    Returns None if file doesn't exist or is invalid.

    This is CRITICAL for data migration - we must preserve existing UUIDs
    so that entities linked to the old UUID don't become orphaned.
    """
    from pathlib import Path
    from uuid import UUID

    if not vault_path:
        # Default to current directory or environment variable
        vault_path = os.getenv("VAULT_PATH", ".")

    path_obj = Path(vault_path)
    config_dir = path_obj / ".writeros"
    id_file = config_dir / "vault_id"

    if id_file.exists():
        try:
            uuid_str = id_file.read_text().strip()
            vault_uuid = UUID(uuid_str)
            logger.info("found_existing_vault_uuid", uuid=str(vault_uuid), path=str(id_file))
            return vault_uuid
        except (ValueError, OSError) as e:
            logger.warning("invalid_vault_id_file", path=str(id_file), error=str(e))
            return None

    logger.info("no_existing_vault_uuid", path=str(id_file))
    return None


def write_uuid_to_filesystem(vault_uuid: "UUID", vault_path: str = None):
    """
    Write vault UUID to filesystem for persistence.
    """
    from pathlib import Path

    if not vault_path:
        vault_path = os.getenv("VAULT_PATH", ".")

    path_obj = Path(vault_path)
    config_dir = path_obj / ".writeros"
    config_dir.mkdir(exist_ok=True)

    id_file = config_dir / "vault_id"
    id_file.write_text(str(vault_uuid))
    logger.info("wrote_vault_uuid_to_disk", uuid=str(vault_uuid), path=str(id_file))


def get_directory_name(vault_path: str = None) -> str:
    """
    Extract directory name for use as vault name.
    E.g., "/data/The_Winds_of_Winter/" -> "The Winds of Winter"
    """
    from pathlib import Path

    if not vault_path:
        vault_path = os.getenv("VAULT_PATH", ".")

    path_obj = Path(vault_path).resolve()
    dir_name = path_obj.name

    # Clean up underscores and common patterns
    clean_name = dir_name.replace("_", " ").strip()

    # Fallback if empty or just "."
    if not clean_name or clean_name == ".":
        clean_name = "My Story"

    return clean_name


def get_or_create_vault_id(vault_path: str) -> "UUID":
    """
    DEPRECATED: Use ensure_vault_in_database() instead.

    Gets the vault ID from .writeros/vault_id or creates a new one.
    This is kept for backward compatibility but should not be used
    for new code - use the full init_db() flow instead.
    """
    logger.warning("deprecated_function", function="get_or_create_vault_id",
                   recommendation="Use ensure_vault_in_database()")

    existing_uuid = read_uuid_from_filesystem(vault_path)
    if existing_uuid:
        return existing_uuid

    from uuid import uuid4
    new_id = uuid4()
    write_uuid_to_filesystem(new_id, vault_path)
    return new_id

if __name__ == "__main__":
    init_db()