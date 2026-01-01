from pydantic import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres@localhost:5432/goride"
    REDIS_URL: str = "redis://localhost:6379/0"
    MATCH_RADIUS_KM: float = 5.0
    ASSIGNMENT_TTL_SEC: int = 10
    
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = -1
    DB_ECHO: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
