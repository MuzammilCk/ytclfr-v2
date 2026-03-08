"""Backward-compatible re-export for database primitives."""

from ytclfr_infra.db.database import Base, build_engine, build_session_factory, session_scope

__all__ = ["Base", "build_engine", "build_session_factory", "session_scope"]
