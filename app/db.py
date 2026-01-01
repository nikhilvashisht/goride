from sqlalchemy import create_engine, MetaData
from contextlib import contextmanager
from .config import settings

# Engine configured for DB URL from settings
engine = create_engine(settings.DATABASE_URL)
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
