from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from bot.config import DATABASE_URL
from database.models import Base
from sqlalchemy import text

# Корректная обработка префиксов для async SQLAlchemy
if DATABASE_URL.startswith("sqlite"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
elif DATABASE_URL.startswith("postgres://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    ASYNC_DATABASE_URL = DATABASE_URL

engine_kwargs = {"echo": False}
if ASYNC_DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"timeout": 20}

engine = create_async_engine(ASYNC_DATABASE_URL, **engine_kwargs)

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
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_until TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_ai_count INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_ai_request_date TIMESTAMP",
    ]

    is_sqlite = ASYNC_DATABASE_URL.startswith("sqlite")
    for migration in migrations:
        sql = migration.replace("IF NOT EXISTS ", "") if is_sqlite else migration
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
        except Exception:
            # Колонка уже создана или миграция применена ранее
            pass


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session