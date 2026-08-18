from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import AdminUser, DbSession, JwtOnlyAdmin
from app.enums import UserRole
from app.schemas.admin import AdminUserCreate, AdminUserOut, AdminUserUpdate, PasswordSet
from app.schemas.common import Page
from app.services.admin import users as service

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin"])


@router.get("", response_model=Page[AdminUserOut])
async def list_users(
    user: AdminUser,
    session: DbSession,
    q: str | None = None,
    department_id: int | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[AdminUserOut]:
    return await service.list_users(
        session,
        filters=service.UserFilters(
            q=q,
            department_id=department_id,
            role=role,
            is_active=is_active,
            page=page,
            size=size,
        ),
    )


@router.post("", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreate, user: AdminUser, session: DbSession
) -> AdminUserOut:
    return await service.create_user(session, payload=payload)


@router.get("/{user_id}", response_model=AdminUserOut)
async def get_user(user_id: int, user: AdminUser, session: DbSession) -> AdminUserOut:
    return await service.get_user(session, user_id=user_id)


@router.patch("/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: int, payload: AdminUserUpdate, user: AdminUser, session: DbSession
) -> AdminUserOut:
    return await service.update_user(session, actor=user, user_id=user_id, payload=payload)


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def set_password(
    user_id: int, payload: PasswordSet, user: JwtOnlyAdmin, session: DbSession
) -> None:
    """**로그인 세션 전용.** API Key로는 호출할 수 없다 — 키가 JWT로 승격되는 경로를 막는다."""
    await service.set_password(session, user_id=user_id, payload=payload)
