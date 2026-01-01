from pydantic_settings import BaseSettings
from pathlib import Path
import yaml


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres@localhost:5432/goride"
    REDIS_URL: str = "redis://localhost:6379/0"
    MATCH_RADIUS_KM: float = 5.0
    ASSIGNMENT_TTL_SEC: int = 10
    
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = -1
    DB_ECHO: bool = False

    # Load .env located next to this file (app/.env) so defaults are overridden
    model_config = {"env_file": str(Path(__file__).resolve().parent / ".env")}


def load_settings() -> Settings:
    """Load settings from application.yaml and merge with environment variables."""
    config_path = Path(__file__).resolve().parent / "application.yaml"
    
    # Start with defaults
    config_dict = {}
    
    # Load from YAML if it exists
    if config_path.exists():
        with open(config_path, "r") as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                # Map YAML structure to Settings fields
                if "database" in yaml_config:
                    db = yaml_config["database"]
                    config_dict["DATABASE_URL"] = db.get("url")
                    config_dict["DB_POOL_SIZE"] = db.get("pool_size")
                    config_dict["DB_MAX_OVERFLOW"] = db.get("max_overflow")
                    config_dict["DB_POOL_TIMEOUT"] = db.get("pool_timeout")
                    config_dict["DB_POOL_RECYCLE"] = db.get("pool_recycle")
                    config_dict["DB_ECHO"] = db.get("echo")
                
                if "redis" in yaml_config:
                    config_dict["REDIS_URL"] = yaml_config["redis"].get("url")
                
                if "matching" in yaml_config:
                    match = yaml_config["matching"]
                    config_dict["MATCH_RADIUS_KM"] = match.get("radius_km")
                    config_dict["ASSIGNMENT_TTL_SEC"] = match.get("assignment_ttl_sec")
    
    # Create Settings with YAML values, but allow env vars to override
    return Settings(**{k: v for k, v in config_dict.items() if v is not None})


settings = load_settings()
