"""부서 마스터 CRUD.

부서 트리의 순환(A→B→A)은 검사하지 않는다. 자기 자신만 막는다 — 데모 조직은 2단계이고,
일반 순환 검출은 재귀 조회가 필요해 값에 비해 비싸다. 이 한계는 phase-status에 남긴다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError, ValidationError
from app.models import Department
from app.schemas.admin import DepartmentCreate, DepartmentOut, DepartmentUpdate
from app.services.admin.common import assert_unique, delete_entity


async def list_departments(session: AsyncSession) -> list[DepartmentOut]:
    rows = (
        (await session.execute(select(Department).order_by(Department.code))).scalars().all()
    )
    return [DepartmentOut.model_validate(row) for row in rows]


async def _load(session: AsyncSession, department_id: int) -> Department:
    department = await session.get(Department, department_id)
    if department is None:
        raise NotFoundError("DEPARTMENT_NOT_FOUND", f"존재하지 않는 부서입니다: {department_id}")
    return department


async def _assert_parent(
    session: AsyncSession, parent_id: int | None, *, self_id: int | None = None
) -> None:
    if parent_id is None:
        return
    if self_id is not None and parent_id == self_id:
        raise ValidationError(
            "INVALID_PARENT", "자기 자신을 상위 부서로 지정할 수 없습니다", field="parent_id"
        )
    if await session.get(Department, parent_id) is None:
        raise ValidationError(
            "INVALID_PARENT", f"존재하지 않는 상위 부서입니다: {parent_id}", field="parent_id"
        )


async def create_department(
    session: AsyncSession, *, payload: DepartmentCreate
) -> DepartmentOut:
    await assert_unique(
        session,
        Department.code,
        payload.code,
        code="DUPLICATE_DEPARTMENT_CODE",
        message=f"이미 있는 부서 코드입니다: {payload.code}",
        field="code",
    )
    await _assert_parent(session, payload.parent_id)
    department = Department(code=payload.code, name=payload.name, parent_id=payload.parent_id)
    session.add(department)
    await session.commit()
    await session.refresh(department)
    return DepartmentOut.model_validate(department)


async def update_department(
    session: AsyncSession, *, department_id: int, payload: DepartmentUpdate
) -> DepartmentOut:
    department = await _load(session, department_id)
    # exclude_unset이 "안 보냄"과 "null로 지우기"를 가르는 유일한 수단이다.
    changes = payload.model_dump(exclude_unset=True)
    if "parent_id" in changes:
        await _assert_parent(session, changes["parent_id"], self_id=department.id)
    for field, value in changes.items():
        setattr(department, field, value)
    await session.commit()
    await session.refresh(department)
    return DepartmentOut.model_validate(department)


async def delete_department(session: AsyncSession, *, department_id: int) -> None:
    department = await _load(session, department_id)
    await delete_entity(
        session,
        department,
        message="이 부서를 참조하는 사용자·센터가 있어 삭제할 수 없습니다",
    )
