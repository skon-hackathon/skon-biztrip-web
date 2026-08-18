from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import AuthError, ForbiddenError
from app.models import User
from app.security import decode_access_token
from app.services.api_keys import authenticate_key

DbSession = Annotated[AsyncSession, Depends(get_db)]

#: Agent가 쓰는 헤더 이름 (spec 7).
API_KEY_HEADER = "X-API-Key"


class _Unrestricted:
    """JWT 인증에는 스코프 제한이 없음을 나타내는 센티널."""

    def __repr__(self) -> str:  # pragma: no cover - 디버깅 편의용
        return "UNRESTRICTED"


UNRESTRICTED = _Unrestricted()


async def _authenticate_jwt(request: Request, session: AsyncSession) -> User:
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise AuthError("MISSING_CREDENTIALS", "인증 정보가 없습니다")

    user_id = decode_access_token(header.split(" ", 1)[1].strip())
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("INVALID_TOKEN", "유효하지 않은 토큰입니다")
    return user


async def get_principal(request: Request, session: DbSession) -> User:
    """JWT 또는 API Key로 인증한다. 웹과 Agent가 같은 라우터를 쓰는 지점이다.

    두 헤더가 동시에 오면 `X-API-Key`가 이긴다. 브라우저는 로그인해 있으면 항상
    Authorization을 보내므로, 키를 명시적으로 얹은 쪽이 더 구체적인 의도이고
    무엇보다 우선순위가 결정적이어야 한다.
    """
    api_key = request.headers.get(API_KEY_HEADER)
    if api_key:
        user, scopes = await authenticate_key(session, api_key.strip())
        # 여기서 commit하는 이유: last_used_at은 요청의 성패와 무관하게 남아야 한다.
        # 이후 서비스가 실패해 롤백해도 "이 키가 쓰였다"는 사실은 지워지면 안 된다.
        # 아직 아무 도메인 작업도 시작되지 않은 시점이라 다른 트랜잭션을 끊지 않는다.
        await session.commit()
        request.state.scopes = scopes
        request.state.auth_method = "api_key"
        return user

    user = await _authenticate_jwt(request, session)
    # UNRESTRICTED 센티널을 쓰는 이유: None을 쓰면 "제한 없음"과 "get_principal이 아예
    # 실행되지 않음"이 구분되지 않는다. 스코프 검사기가 기본값으로 읽는 순간,
    # 의존성을 빠뜨린 엔드포인트가 조용히 전체 권한을 얻는다.
    request.state.scopes = UNRESTRICTED
    request.state.auth_method = "jwt"
    return user


CurrentUser = Annotated[User, Depends(get_principal)]


def require_role(*roles: str):
    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("FORBIDDEN_ROLE", "권한이 없습니다")
        return user

    return checker
