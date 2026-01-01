from redis import Redis
from .config import settings


redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


def ping() -> bool:
    try:
        return redis_client.ping()
    except Exception:
        return False
