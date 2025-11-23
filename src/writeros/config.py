from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "WriterOS"
    database_url: str = "sqlite:///./writeros.db"
    APP_ENV: str = "local" # or "production"
    LOG_LEVEL: str = "INFO" # DEBUG, INFO, WARNING, ERROR
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
