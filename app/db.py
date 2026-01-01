from sqlalchemy import create_engine, MetaData
from contextlib import contextmanager
from .config import settings

# Engine configured for DB URL from settings
# Use pool settings from config (defaults match SQLAlchemy QueuePool defaults)
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=settings.DB_ECHO,
)
metadata = MetaData()


@contextmanager
def get_conn():
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    from .models import metadata as models_metadata
    models_metadata.create_all(bind=engine)
