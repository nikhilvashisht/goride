
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from contextlib import asynccontextmanager
from .config import settings

# Ensure the DATABASE_URL uses an async driver (asyncpg) for SQLAlchemy asyncio
if settings.DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in settings.DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL must use an async driver for async SQLAlchemy (e.g. postgresql+asyncpg://...). "
        "Update your DATABASE_URL or set the DATABASE_URL environment variable accordingly."
    )

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO
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
