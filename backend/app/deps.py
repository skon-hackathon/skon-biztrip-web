from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import AuthError, ForbiddenError
from app.models import User
from app.security import decode_access_token
from app.services.api_keys import authenticate_key
from app.services.api_scopes import required_scope_for

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


def _enforce_scope(request: Request) -> None:
    """이 요청이 이 엔드포인트를 부를 스코프를 가졌는지 본다.

    검사가 여기 한 곳에만 있는 것이 핵심이다. 엔드포인트마다 의존성을 붙이는 방식은
    빠뜨릴 수 있고, 빠뜨린 결과가 fail-open(그 엔드포인트만 전권)이다.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path is None:  # pragma: no cover - 라우팅된 요청에는 항상 route가 있다
        raise ForbiddenError("SCOPE_UNDECLARED", "경로를 확인할 수 없습니다")

    required = required_scope_for(request.method, path)
    scopes = request.state.scopes
    # 센티널과의 **동일성** 비교. `if not scopes`나 `getattr(..., None)`로 바꾸면
    # 스코프가 빈 키가 전권을 얻는다.
    if scopes is UNRESTRICTED:
        return
    if required is None:
        return
    if str(required) not in scopes:
        raise ForbiddenError(
            "SCOPE_REQUIRED", f"이 요청에는 {required} 스코프가 필요합니다"
        )


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
    else:
        user = await _authenticate_jwt(request, session)
        # UNRESTRICTED 센티널을 쓰는 이유: None을 쓰면 "제한 없음"과 "get_principal이 아예
        # 실행되지 않음"이 구분되지 않는다. 스코프 검사기가 기본값으로 읽는 순간,
        # 의존성을 빠뜨린 엔드포인트가 조용히 전체 권한을 얻는다.
        request.state.scopes = UNRESTRICTED
        request.state.auth_method = "jwt"

    _enforce_scope(request)
    return user


CurrentUser = Annotated[User, Depends(get_principal)]


def require_role(*roles: str):
    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("FORBIDDEN_ROLE", "권한이 없습니다")
        return user

    return checker


async def get_jwt_principal(request: Request, user: CurrentUser) -> User:
    """로그인 세션(JWT)에서만 허용하는 엔드포인트용.

    API Key로 새 API Key를 만들 수 있으면 스코프 제한이 통째로 무의미해진다 —
    `cards:read` 키 하나로 전권 키를 찍어낼 수 있게 된다. 그래서 키 관리 API는
    사람이 로그인한 세션에서만 열린다.

    `get_principal`을 거쳐 오므로 스코프 표 소진 가드도 이 라우트를 함께 검사한다.
    auth_method가 없으면(=예상 못 한 경로) 통과가 아니라 거부다.
    """
    if getattr(request.state, "auth_method", None) != "jwt":
        raise ForbiddenError("API_KEY_FORBIDDEN", "이 작업은 로그인 세션에서만 가능합니다")
    return user


JwtOnlyUser = Annotated[User, Depends(get_jwt_principal)]
