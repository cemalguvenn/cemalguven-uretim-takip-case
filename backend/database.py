"""Async SQLAlchemy engine, session factory, and schema creation."""
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import get_settings
from models import Base

_settings = get_settings()

engine: AsyncEngine = create_async_engine(_settings.database_url, echo=False, future=True)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@event.listens_for(engine.sync_engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    """WAL lets a background import write while the UI keeps polling (reads)."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


def _migrate_validation_rules(sync_conn) -> None:
    """Add columns introduced after the table was first created.

    `create_all` only creates missing tables, never new columns, so an existing
    `production.db` needs a lightweight ALTER. Idempotent: each column is added
    only if absent, so it's safe to run on every startup.
    """
    from sqlalchemy import inspect

    cols = {c["name"] for c in inspect(sync_conn).get_columns("validation_rules")}
    adds = {
        "rule_type": "ALTER TABLE validation_rules "
                     "ADD COLUMN rule_type VARCHAR NOT NULL DEFAULT 'builtin'",
        "target_field": "ALTER TABLE validation_rules ADD COLUMN target_field VARCHAR",
        "comparison": "ALTER TABLE validation_rules ADD COLUMN comparison VARCHAR",
    }
    for name, ddl in adds.items():
        if name not in cols:
            sync_conn.exec_driver_sql(ddl)


async def init_db() -> None:
    """Create all tables if they do not exist, then apply column migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_validation_rules)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a scoped async session."""
    async with SessionLocal() as session:
        yield session
