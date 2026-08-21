"""운영 DB에 대한 스키마 생성·시드를 **사람이 명시적으로** 실행하는 CLI.

앱 기동 시에는 아무것도 자동 실행하지 않는다. 이미 운영 중인 DB에 붙기 때문에
자동 DDL이나 자동 시드는 남의 데이터를 건드릴 위험이 있다.

    uv run python -m app.cli check      # 접속 확인만
    uv run python -m app.cli init-db    # 스키마 + 테이블 생성 (기존 데이터 보존)
    uv run python -m app.cli seed       # 데모 데이터 적재 (멱등)
"""

import argparse
import asyncio
import sys

from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.models import Base
from app.seed import seed_all


def _target() -> str:
    s = get_settings()
    return (
        f"{s.db_user}@{s.db_host}:{s.db_port}/{s.db_name} "
        f"(schema={s.db_schema}, user 테이블={s.user_db_schema})"
    )


async def check() -> None:
    async with SessionLocal() as session:
        version = (await session.execute(text("SELECT version()"))).scalar_one()
        schema = (await session.execute(text("SELECT current_schema()"))).scalar_one_or_none()
        tables = (
            await session.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = current_schema()"
                )
            )
        ).scalar_one()
    print(f"연결됨: {_target()}")
    print(f"  서버: {version.split(',')[0]}")
    print(f"  current_schema: {schema}")
    print(f"  해당 스키마의 테이블 수: {tables}")


async def init_db() -> None:
    settings = get_settings()
    # user 테이블은 다른 프로젝트와 공유하려고 별도 스키마(기본 public)에 있다.
    schemas = dict.fromkeys([settings.db_schema, settings.user_db_schema])
    async with engine.begin() as conn:
        for schema in schemas:
            # 스키마명은 위에서 식별자 검증을 거친 값이다 (app.config.assert_safe_identifier).
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.run_sync(Base.metadata.create_all)
    print(f"스키마·테이블 준비 완료: {_target()}")
    print("  기존 테이블은 그대로 두고 없는 것만 만든다. 컬럼 변경은 반영하지 않는다.")


async def seed() -> None:
    async with SessionLocal() as session:
        await seed_all(session)
    print(f"시드 완료 (멱등): {_target()}")


COMMANDS = {"check": check, "init-db": init_db, "seed": seed}


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args()

    try:
        asyncio.run(COMMANDS[args.command]())
    except Exception as exc:  # noqa: BLE001 - CLI 최상단에서 사람이 읽을 메시지로 바꾼다
        print(f"실패: {exc}", file=sys.stderr)
        print(f"  대상: {_target()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
