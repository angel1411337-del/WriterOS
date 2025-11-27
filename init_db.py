from sqlmodel import SQLModel
from writeros.utils.db import engine
# Import all models to ensure they are registered with SQLModel
from writeros.schema import *

def init_db():
    print("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()
