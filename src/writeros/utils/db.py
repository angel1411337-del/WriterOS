from src.writeros.core.logging import get_logger
from sqlmodel import create_engine, SQLModel, Session, text
import time

logger = get_logger(__name__)

# Connection string
DATABASE_URL = "postgresql://writer:password@localhost:5432/writeros"

# Create the Engine
engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    """
    Initializes the database.
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
            from src.writeros import schema

            # 3. Create Tables
            SQLModel.metadata.create_all(engine)

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