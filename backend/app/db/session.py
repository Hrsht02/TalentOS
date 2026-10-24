import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


_engine_kwargs = {"pool_pre_ping": True}

if os.getenv("DISABLE_DB_POOL") == "1":
    # Scheduled runners call asyncio.run() repeatedly, so do not retain
    # asyncpg connections across the short-lived event loops.
    _engine_kwargs["poolclass"] = NullPool
else:
    # Keep the existing pooled configuration for the normal Celery worker.
    _engine_kwargs["pool_size"] = settings.db_pool_size
    _engine_kwargs["max_overflow"] = settings.db_max_overflow

engine = create_async_engine(settings.database_url, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
