from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from rag_platform_auth_middleware import set_tenant_guc

engine_args: dict = {"echo": False, "future": True}

if not settings.database_url.startswith("sqlite"):
    engine_args.update(
        {
            "pool_pre_ping": True,
            "pool_size": 5,
            "max_overflow": 10,
        }
    )

engine = create_async_engine(settings.database_url, **engine_args)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        await set_tenant_guc(session, getattr(request.state, "tenant_id", None))
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
