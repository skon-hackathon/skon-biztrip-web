from fastapi import APIRouter, status

from app.deps import AdminUser, DbSession
from app.schemas.admin import (
    AdminCodeGroupOut,
    AdminCodeOut,
    CodeCreate,
    CodeGroupCreate,
    CodeGroupUpdate,
    CodeUpdate,
)
from app.services.admin import codes as service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/code-groups", response_model=list[AdminCodeGroupOut])
async def list_code_groups(user: AdminUser, session: DbSession) -> list[AdminCodeGroupOut]:
    return await service.list_code_groups(session)


@router.post(
    "/code-groups", response_model=AdminCodeGroupOut, status_code=status.HTTP_201_CREATED
)
async def create_code_group(
    payload: CodeGroupCreate, user: AdminUser, session: DbSession
) -> AdminCodeGroupOut:
    return await service.create_code_group(session, payload=payload)


@router.patch("/code-groups/{group_id}", response_model=AdminCodeGroupOut)
async def update_code_group(
    group_id: int, payload: CodeGroupUpdate, user: AdminUser, session: DbSession
) -> AdminCodeGroupOut:
    return await service.update_code_group(session, group_id=group_id, payload=payload)


@router.delete("/code-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_code_group(group_id: int, user: AdminUser, session: DbSession) -> None:
    await service.delete_code_group(session, group_id=group_id)


@router.post(
    "/code-groups/{group_id}/codes",
    response_model=AdminCodeOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_code(
    group_id: int, payload: CodeCreate, user: AdminUser, session: DbSession
) -> AdminCodeOut:
    return await service.create_code(session, group_id=group_id, payload=payload)


@router.patch("/codes/{code_id}", response_model=AdminCodeOut)
async def update_code(
    code_id: int, payload: CodeUpdate, user: AdminUser, session: DbSession
) -> AdminCodeOut:
    return await service.update_code(session, code_id=code_id, payload=payload)


@router.delete("/codes/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_code(code_id: int, user: AdminUser, session: DbSession) -> None:
    await service.delete_code(session, code_id=code_id)
