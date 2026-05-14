"""Pydantic settings and env vars."""

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings."""
    OPENAI_API_KEY: str = ""
    GITHUB_PAT: str = ""
    GITHUB_REPO: str = "" # format: owner/repo
    MODEL_NAME: str = "gpt-4o"
    CHROMA_PERSIST_DIR: str = ".chromadb"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
