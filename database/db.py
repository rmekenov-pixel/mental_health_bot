from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from bot.config import DATABASE_URL
from database.models import Base
from sqlalchemy import text
from sqlalchemy.engine import make_url

ASYNC_DRIVERS = {
    "sqlite": "sqlite+aiosqlite",
    "postgres": "postgresql+asyncpg",
    "postgresql": "postgresql+asyncpg",
}

engine_url = make_url(DATABASE_URL)
dialect = engine_url.drivername.split("+")[0]
if dialect in ASYNC_DRIVERS:
    engine_url = engine_url.set(drivername=ASYNC_DRIVERS[dialect])

engine_kwargs = {"echo": False}
if dialect == "sqlite":
    engine_kwargs["connect_args"] = {"timeout": 20}

engine = create_async_engine(engine_url, **engine_kwargs)

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

    is_sqlite = dialect == "sqlite"
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