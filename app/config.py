from pydantic import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./goride.db"
    REDIS_URL: str | None = None
    MATCH_RADIUS_KM: float = 5.0
    ASSIGNMENT_TTL_SEC: int = 10
    H3_RESOLUTION: int = 8
    H3_MAX_K_RING: int = 2

    class Config:
        env_file = ".env"


settings = Settings()
