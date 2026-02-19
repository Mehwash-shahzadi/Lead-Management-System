from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(env_file=".env", case_sensitive=True)

    DATABASE_URL: str
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Redis configuration for caching and duplicate detection
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 300  # 5 minutes default for dashboard cache
    REDIS_DUPLICATE_CHECK_TTL: int = 86400  # 24 hours for duplicate lead detection

    # Business rule configuration
    MAX_AGENT_LEADS: int = 50
    DUPLICATE_CHECK_HOURS: int = 24
    FOLLOW_UP_CONFLICT_WINDOW_MINUTES: int = 30
    OVERDUE_TASK_MAX_DAYS: int = 30

    # CORS configuration — comma-separated origins
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    PROPERTY_SERVICE_URL: str = ""


settings = Settings()
