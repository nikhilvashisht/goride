from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from contextlib import asynccontextmanager
from .config import settings

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
)
metadata = MetaData()


@asynccontextmanager
async def get_conn():
    async with engine.connect() as conn:
        yield conn


async def init_db():
    from .models import metadata as models_metadata
    async with engine.begin() as conn:
        await conn.run_sync(models_metadata.create_all)
