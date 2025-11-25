from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    app_name: str = "WriterOS"

    # ⚠️ PostgreSQL REQUIRED - WriterOS uses pgvector extension
    # SQLite is NOT supported
    database_url: str = os.getenv("DATABASE_URL", "")

    # Application Mode: "local" (Obsidian) or "saas" (Cloud)
    writeros_mode: str = os.getenv("WRITEROS_MODE", "local")

    # Generic environment (debug/prod)
    APP_ENV: str = "local"  # or "production"
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Validate PostgreSQL requirement
if not settings.database_url:
    raise ValueError(
        "DATABASE_URL environment variable is required.\n"
        "WriterOS requires PostgreSQL with pgvector extension.\n"
        "Example: DATABASE_URL=postgresql://user:password@localhost:5432/writeros"
    )

if not settings.database_url.startswith("postgresql"):
    raise ValueError(
        f"Invalid DATABASE_URL: {settings.database_url}\n"
        "WriterOS requires PostgreSQL (not SQLite or other databases).\n"
        "SQLite does not support the pgvector extension required for semantic search.\n"
        "Please set DATABASE_URL to a PostgreSQL connection string."
    )
