import os
from collections.abc import AsyncGenerator

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import assert_safe_identifier, get_settings
from app.db import build_engine, get_db
from app.main import app
from app.models import Base

#: 테스트는 앱과 같은 DB 서버의 **별도 스키마**에서 돈다. 절대 앱 스키마를 쓰지 않는다.
TEST_SCHEMA = os.getenv("TEST_DB_SCHEMA", "skon_test")


@pytest.fixture(scope="session")
async def test_engine():
    settings = get_settings()
    assert_safe_identifier(TEST_SCHEMA, field="TEST_DB_SCHEMA")

    # 이 가드가 없으면 아래 drop_all이 운영 스키마의 테이블을 통째로 지운다.
    if TEST_SCHEMA == settings.db_schema:
        pytest.exit(
            f"TEST_DB_SCHEMA({TEST_SCHEMA})가 앱의 DB_SCHEMA와 같습니다. "
            "테스트는 매 실행마다 drop_all을 수행하므로 반드시 다른 스키마를 지정하십시오.",
            returncode=1,
        )

    # build_engine은 search_path를 이 스키마 하나로만 고정한다. public이 fallback으로
    # 남지 않으므로 언퀄리파이드 DDL이 다른 스키마로 새어나갈 수 없다.
    engine = build_engine(settings.database_url, TEST_SCHEMA)
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TEST_SCHEMA}"'))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """각 테스트를 외부 트랜잭션 안에서 실행하고 끝나면 롤백한다."""
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
async def client(db_session) -> AsyncGenerator[httpx.AsyncClient, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
