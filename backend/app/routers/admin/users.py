from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import AdminUser, DbSession, JwtOnlyAdmin
from app.enums import UserRole, UserStatus
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    PasswordSet,
    UserApprove,
)
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
    status: UserStatus | None = None,
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
            status=status,
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


@router.post("/{user_id}/approve", response_model=AdminUserOut)
async def approve_user(
    user_id: int, payload: UserApprove, user: AdminUser, session: DbSession
) -> AdminUserOut:
    """가입 승인. 관리자가 사번·직급·결재자·역할을 채우면 계정이 열린다."""
    return await service.approve_user(session, user_id=user_id, payload=payload)


@router.post("/{user_id}/reject", response_model=AdminUserOut)
async def reject_user(user_id: int, user: AdminUser, session: DbSession) -> AdminUserOut:
    """가입 거절. 행은 남으므로 같은 이메일로 재신청할 수 있다."""
    return await service.reject_user(session, user_id=user_id)
