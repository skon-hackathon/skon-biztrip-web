from fastapi import APIRouter, status

from app.deps import AdminUser, DbSession
from app.schemas.admin import DepartmentCreate, DepartmentOut, DepartmentUpdate
from app.services.admin import departments as service

router = APIRouter(prefix="/api/v1/admin/departments", tags=["admin"])


@router.get("", response_model=list[DepartmentOut])
async def list_departments(user: AdminUser, session: DbSession) -> list[DepartmentOut]:
    return await service.list_departments(session)


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate, user: AdminUser, session: DbSession
) -> DepartmentOut:
    return await service.create_department(session, payload=payload)


@router.patch("/{department_id}", response_model=DepartmentOut)
async def update_department(
    department_id: int, payload: DepartmentUpdate, user: AdminUser, session: DbSession
) -> DepartmentOut:
    return await service.update_department(
        session, department_id=department_id, payload=payload
    )


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(department_id: int, user: AdminUser, session: DbSession) -> None:
    await service.delete_department(session, department_id=department_id)
