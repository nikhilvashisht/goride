from redis.asyncio import Redis
from .config import settings


redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def ping() -> bool:
    try:
        return await redis_client.ping()
    except Exception:
        return False
