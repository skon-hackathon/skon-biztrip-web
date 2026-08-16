import re
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Settings(BaseSettings):
    """이 프로젝트는 DB를 직접 띄우지 않고 이미 운영 중인 PostgreSQL에 접속한다.

    접속 정보는 전부 환경변수로 주입한다. `.env.example` 참고.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "skon"
    db_password: str = "skon"
    db_name: str = "skon"
    db_schema: str = "skon"

    jwt_secret: str = "dev-only-insecure-secret-do-not-use-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    @property
    def database_url(self) -> str:
        """asyncpg 접속 URL. 비밀번호에 `@`·`#` 같은 문자가 있어도 안전하도록 인코딩한다."""
        return (
            f"postgresql+asyncpg://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


def assert_safe_identifier(name: str, *, field: str) -> str:
    """스키마명을 DDL에 문자열로 끼워 넣기 전에 검증한다.

    스키마명은 바인드 파라미터로 넘길 수 없어 문자열 보간이 불가피하므로,
    평범한 식별자가 아니면 아예 거부해 SQL 주입 경로를 차단한다.
    """
    if not _IDENTIFIER.match(name):
        raise ValueError(f"{field}은(는) 영문자·숫자·밑줄만 쓸 수 있습니다: {name!r}")
    return name


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    assert_safe_identifier(settings.db_schema, field="DB_SCHEMA")
    return settings
