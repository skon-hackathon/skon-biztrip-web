from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import AuthError, ForbiddenError
from app.models import User
from app.security import decode_access_token

DbSession = Annotated[AsyncSession, Depends(get_db)]


class _Unrestricted:
    """JWT 인증에는 스코프 제한이 없음을 나타내는 센티널."""

    def __repr__(self) -> str:  # pragma: no cover - 디버깅 편의용
        return "UNRESTRICTED"


UNRESTRICTED = _Unrestricted()


async def get_principal(request: Request, session: DbSession) -> User:
    """JWT 또는 API Key로 인증한다. Phase 1은 JWT 분기만 구현한다."""
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise AuthError("MISSING_CREDENTIALS", "인증 정보가 없습니다")

    user_id = decode_access_token(header.split(" ", 1)[1].strip())
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("INVALID_TOKEN", "유효하지 않은 토큰입니다")

    # UNRESTRICTED 센티널을 쓰는 이유: None을 쓰면 "제한 없음"과 "get_principal이 아예
    # 실행되지 않음"이 구분되지 않는다. Phase 4에서 스코프 검사기가
    # getattr(request.state, "scopes", None)로 읽는 순간, 의존성을 빠뜨린 엔드포인트가
    # 조용히 전체 권한을 얻게 된다. 센티널이면 그 경우 fail-closed가 된다.
    request.state.scopes = UNRESTRICTED
    return user


CurrentUser = Annotated[User, Depends(get_principal)]


def require_role(*roles: str):
    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("FORBIDDEN_ROLE", "권한이 없습니다")
        return user

    return checker
