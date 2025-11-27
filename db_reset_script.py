from sqlmodel import SQLModel, Session, text
from writeros.utils.db import engine
# Explicitly import modules to ensure registration
from writeros.schema import identity, library, world, psychology, narrative, session, theme, logistics, prose, project, mechanics, api, graph, temporal_anchoring, extended_universe, universe_manifest
# Also import Vault directly to be safe
from writeros.schema.identity import Vault

def reset_db():
    print("Enabling vector extension...")
    with Session(engine) as session:
        session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
        session.commit()

    print("Dropping all tables...")
    SQLModel.metadata.drop_all(engine)
    
    print("Registered tables in metadata:")
    for table_name in SQLModel.metadata.tables.keys():
        print(f"- {table_name}")
        
    print("Creating all tables...")
    SQLModel.metadata.create_all(engine)
    print("Database reset complete.")

if __name__ == "__main__":
    reset_db()
