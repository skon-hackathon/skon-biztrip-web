import pytest

from app.config import Settings, assert_safe_identifier


def _settings(monkeypatch, **overrides: str) -> Settings:
    defaults = {
        "DB_HOST": "db.example.com",
        "DB_PORT": "6432",
        "DB_USER": "skon_app",
        "DB_PASSWORD": "s3cret",
        "DB_NAME": "corp",
        "DB_SCHEMA": "biztrip",
        "JWT_SECRET": "unit-test-secret-that-is-long-enough-32",
    }
    for key, value in {**defaults, **overrides}.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_settings_read_connection_parts_from_env(monkeypatch):
    settings = _settings(monkeypatch)

    assert settings.db_host == "db.example.com"
    assert settings.db_port == 6432
    assert settings.db_schema == "biztrip"
    assert settings.jwt_expire_hours == 8


def test_database_url_is_assembled_from_parts(monkeypatch):
    settings = _settings(monkeypatch)

    assert settings.database_url == "postgresql+asyncpg://skon_app:s3cret@db.example.com:6432/corp"


def test_database_url_escapes_credentials(monkeypatch):
    """운영 DB 비밀번호에는 URL을 깨뜨리는 문자가 흔히 들어간다."""
    settings = _settings(monkeypatch, DB_PASSWORD="p@ss/w#rd", DB_USER="svc user")

    assert "p%40ss%2Fw%23rd" in settings.database_url
    assert "svc+user" in settings.database_url
    assert settings.database_url.endswith("@db.example.com:6432/corp")


@pytest.mark.parametrize("bad", ["public;drop", "with space", "1leading", "", 'quo"te'])
def test_assert_safe_identifier_rejects_unsafe_schema_names(bad):
    with pytest.raises(ValueError):
        assert_safe_identifier(bad, field="DB_SCHEMA")


@pytest.mark.parametrize("good", ["skon", "skon_test", "_private", "s1"])
def test_assert_safe_identifier_accepts_plain_identifiers(good):
    assert assert_safe_identifier(good, field="DB_SCHEMA") == good
