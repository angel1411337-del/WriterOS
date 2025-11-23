import sys
import os

# --- 🟢 PATH FIX START ---
# Add the project root to Python's search path so we can import 'agents'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
# --- 🟢 PATH FIX END ---

from sqlmodel import create_engine, SQLModel, Session, text
import time

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
            print(f"Connecting to Database (Attempt {i+1})...")

            # 1. Enable Vector Extension
            with Session(engine) as session:
                session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
                session.commit()

            # 2. Register Tables
            # Now this import will work!
            from agents import schema

            # 3. Create Tables
            SQLModel.metadata.create_all(engine)

            print("PostgreSQL Database Initialized (Tables + Vector).")
            return
        except Exception as e:
            print(f"Error: {e}")
            if i < max_retries - 1:
                print("   Retrying in 2 seconds...")
                time.sleep(2)
            else:
                print("FATAL: Initialization failed.")

def get_session():
    """FastAPI Dependency"""
    with Session(engine) as session:
        yield session

if __name__ == "__main__":
    init_db()