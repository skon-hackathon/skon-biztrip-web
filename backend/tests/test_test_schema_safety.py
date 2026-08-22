import os
from pathlib import Path
import subprocess
import sys

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
COLLECTION_TARGET = BACKEND_DIR / "tests" / "test_config.py"


def _collect_with_schema(
    tmp_path: Path,
    *,
    test_schema: str,
    db_schema: str = "skon",
    user_schema: str = "public",
    use_dotenv: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "DB_SCHEMA": db_schema,
            "USER_DB_SCHEMA": user_schema,
            "PYTHONPATH": str(BACKEND_DIR),
        }
    )

    if use_dotenv:
        env.pop("TEST_DB_SCHEMA", None)
        (tmp_path / ".env").write_text(
            f"TEST_DB_SCHEMA={test_schema}\n",
            encoding="utf-8",
        )
    else:
        env["TEST_DB_SCHEMA"] = test_schema

    # --collect-only는 test_engine fixture를 실행하지 않으므로 회귀 테스트 자체가 DB를
    # 생성하거나 삭제하지 않는다. 보호 로직은 그보다 이른 conftest import에서 동작해야 한다.
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", str(COLLECTION_TARGET)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("test_schema", "db_schema", "user_schema"),
    [
        ("public", "skon", "public"),
        ("skon", "skon", "public"),
        ("accounts", "skon", "accounts"),
        ("scratch", "skon", "public"),
    ],
)
def test_collection_rejects_destructive_test_schemas(
    tmp_path, test_schema, db_schema, user_schema
):
    result = _collect_with_schema(
        tmp_path,
        test_schema=test_schema,
        db_schema=db_schema,
        user_schema=user_schema,
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert "TEST_DB_SCHEMA" in result.stdout + result.stderr


def test_collection_reads_test_schema_from_dotenv_before_guarding(tmp_path):
    result = _collect_with_schema(
        tmp_path,
        test_schema="public",
        use_dotenv=True,
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert "TEST_DB_SCHEMA" in result.stdout + result.stderr


def test_collection_allows_an_isolated_test_schema(tmp_path):
    result = _collect_with_schema(
        tmp_path,
        test_schema="skon_test_gw0",
    )

    assert result.returncode == 0, result.stdout + result.stderr
