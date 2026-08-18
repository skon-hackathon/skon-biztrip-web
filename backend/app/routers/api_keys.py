from fastapi import APIRouter, status

from app.deps import DbSession, JwtOnlyUser
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.services import api_keys as api_key_service

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(user: JwtOnlyUser, session: DbSession) -> list[ApiKeyOut]:
    return await api_key_service.list_keys(session, user=user)


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate, user: JwtOnlyUser, session: DbSession
) -> ApiKeyCreated:
    """평문 키는 이 응답에만 담긴다. 다시 조회할 방법이 없다 (spec 5.7)."""
    return await api_key_service.create_key(session, user=user, payload=payload)


@router.post("/{key_id}/revoke", response_model=ApiKeyOut)
async def revoke_api_key(key_id: int, user: JwtOnlyUser, session: DbSession) -> ApiKeyOut:
    return await api_key_service.revoke_key(session, user=user, key_id=key_id)
