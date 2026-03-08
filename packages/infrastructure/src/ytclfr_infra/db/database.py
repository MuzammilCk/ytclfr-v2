"""SQLAlchemy database primitives for engine and session management."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ytclfr_core.config import Settings
from ytclfr_core.errors.exceptions import RepositoryError


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def build_engine(settings: Settings) -> Engine:
    """Build a production-ready SQLAlchemy engine."""
    try:
        return create_engine(
            str(settings.database_url),
            pool_pre_ping=True,
            future=True,
        )
    except Exception as exc:
        raise RepositoryError("Failed to create database engine.") from exc


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a SQLAlchemy session factory."""
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Provide a transaction-scoped SQLAlchemy session."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
