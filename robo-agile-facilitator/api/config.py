"""Application configuration settings."""
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Get the project root directory (parent of backend/)
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4.1-2025-04-14"
    openai_realtime_model: str = "gpt-4o-realtime-preview-2024-12-17"
    
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "aesf_password_2024"
    # Neo4j database name (Neo4j 4.x+ multi-database support)
    neo4j_database: str = "neo4j"
    
    # Redis
    redis_url: str = "redis://localhost:16379"
    
    # TURN Server
    turn_server: str = "turn:localhost:3478"
    turn_username: str = "aesf_user"
    turn_credential: str = "aesf_turn_pass"
    
    # App Settings
    debug: bool = True
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:5176,http://localhost:5177,http://localhost:3000"
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    class Config:
        env_file = PROJECT_ROOT / ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

