"""Database engine + lifecycle helpers — Phase 1.

Postgres via SQLAlchemy/SQLModel. Connection comes from ``settings.database_url``
(env ``DATABASE_URL`` to point at a hosted DB). Local default targets the
``docker compose`` service in the repo root.

No Alembic: the schema is still churning through Phases 2-3, so ``reset_db()`` just
drops and recreates. The DB is disposable — every seed run resets it.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import settings

ENGINE = create_engine(settings.database_url, echo=False, pool_pre_ping=True)


def init_db() -> None:
    """Create any missing tables. Importing models registers them on the metadata."""
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(ENGINE)


def reset_db() -> None:
    """Drop everything and recreate — used by the seeder and POST /admin/reset."""
    from . import models  # noqa: F401

    SQLModel.metadata.drop_all(ENGINE)
    SQLModel.metadata.create_all(ENGINE)


def get_session() -> Iterator[Session]:
    """FastAPI dependency (used from Phase 3)."""
    with Session(ENGINE) as session:
        yield session
