from fastapi import APIRouter

from app.deps import CurrentUser
from app.schemas.api_key import ScopeInfo
from app.services.api_scopes import scope_catalog

router = APIRouter(prefix="/api/v1", tags=["meta"])


@router.get("/scopes", response_model=list[ScopeInfo])
async def list_scopes(user: CurrentUser) -> list[ScopeInfo]:
    """스코프별 설명과 해당 엔드포인트. `/developers` 가이드와 Agent가 같은 것을 본다.

    `user`를 쓰지 않지만 의존성은 유지한다 — 인증 없이 열면 라우트 목록이 그대로 노출되고,
    무엇보다 스코프 표 소진 가드가 이 라우트를 검사 대상에서 빼버린다.
    """
    return [
        ScopeInfo(scope=entry.scope, description=entry.description, endpoints=entry.endpoints)
        for entry in scope_catalog()
    ]
