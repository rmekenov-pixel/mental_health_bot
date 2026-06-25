from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from bot.config import DATABASE_URL
from database.models import Base
from sqlalchemy import text

# Для SQLite меняем префикс
if DATABASE_URL.startswith("sqlite"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
else:
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS reminder_time VARCHAR DEFAULT '20:00'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS utc_offset INTEGER DEFAULT 5",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR DEFAULT 'ru'",
    ]

    for migration in migrations:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(migration))
        except Exception as e:
            import logging
            logging.error(f"Migration failed: {migration} - {e}")

async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session