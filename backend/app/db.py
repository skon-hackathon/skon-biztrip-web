from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import assert_safe_identifier, get_settings


def build_engine(url: str, schema: str) -> AsyncEngine:
    """지정한 스키마 **하나만** `search_path`에 두는 엔진을 만든다.

    `public`을 fallback으로 남기지 않는 것이 핵심이다. 남겨두면 이름이 겹치는
    테이블에 대한 DDL이나 질의가 의도치 않게 `public`으로 새어나갈 수 있고,
    특히 테스트의 `drop_all`이 운영 스키마의 테이블을 지울 수 있다.
    """
    assert_safe_identifier(schema, field="schema")
    return create_async_engine(
        url,
        echo=False,
        future=True,
        connect_args={"server_settings": {"search_path": schema}},
    )


_settings = get_settings()
engine = build_engine(_settings.database_url, _settings.db_schema)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
