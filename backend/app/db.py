from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()


def _normalize_db_url(url: str) -> str:
    """Coerce Railway-style `postgresql://` URLs to use psycopg 3.

    SQLAlchemy defaults to psycopg2 for the bare `postgresql://` scheme; we ship
    psycopg 3 in requirements.txt because it has a cleaner async story and an
    official binary wheel for 3.13. Also normalize the older `postgres://`
    scheme that some platforms still emit.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


_db_url = _normalize_db_url(settings.database_url)
connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}
engine_kwargs: dict = {"connect_args": connect_args, "future": True}
if _db_url.startswith("postgresql"):
    # Railway's pooler closes idle connections; recycle to dodge stale-conn errors.
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 300
engine = create_engine(_db_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401 — register models on Base.metadata
    Base.metadata.create_all(engine)
