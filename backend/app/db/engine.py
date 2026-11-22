from collections.abc import AsyncGenerator
from pathlib import Path
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import DATA_DIR, env_settings


class Base(DeclarativeBase):
    pass


def _make_engine(db_url: str | None = None):
    url = db_url or env_settings.resolved_database_url()
    if url.startswith("sqlite") and ":memory:" not in url:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = url.split("///", 1)[-1]
        if raw_path and not raw_path.startswith(":"):
            Path(raw_path).parent.mkdir(parents=True, exist_ok=True)

    eng = create_async_engine(url, echo=False, future=True)

    @event.listens_for(eng.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()

    return eng


engine = _make_engine()
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db(target_engine=None) -> None:
    eng = target_engine or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
