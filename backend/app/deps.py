from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import AuthError, ForbiddenError
from app.models import User
from app.security import decode_access_token

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_principal(request: Request, session: DbSession) -> User:
    """JWT 또는 API Key로 인증한다. Phase 1은 JWT 분기만 구현한다."""
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise AuthError("MISSING_CREDENTIALS", "인증 정보가 없습니다")

    user_id = decode_access_token(header.split(" ", 1)[1].strip())
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("INVALID_TOKEN", "유효하지 않은 토큰입니다")

    request.state.scopes = None  # None = 전 권한 (JWT). Phase 4에서 API Key 스코프가 채운다.
    return user


CurrentUser = Annotated[User, Depends(get_principal)]


def require_role(*roles: str):
    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("FORBIDDEN_ROLE", "권한이 없습니다")
        return user

    return checker
