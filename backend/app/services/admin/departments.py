"""부서 마스터 CRUD.

부서 트리의 순환(A→B→A)은 검사하지 않는다. 자기 자신만 막는다 — 데모 조직은 2단계이고,
일반 순환 검출은 재귀 조회가 필요해 값에 비해 비싸다. 이 한계는 phase-status에 남긴다.

삭제 전 사용자 참조를 서비스가 직접 세는 이유: `user` 테이블은 계정 공유 때문에 다른
스키마(기본 public)에 있고, 그 쪽에서 우리 스키마를 역참조하지 않도록 `user.department_id`에
FK를 걸지 않았다. FK가 없으면 `delete_entity`의 IntegrityError 변환이 아무것도 잡지 못해
사람이 딸린 부서가 조용히 지워진다 (`admin/centers.py`의 `_REFERENCES`와 같은 처지다).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import Department, User
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
    # FK가 없는 참조이므로 DB가 막아주지 못한다. 여기가 유일한 방어선이다.
    users = await session.scalar(
        select(func.count()).select_from(User).where(User.department_id == department_id)
    )
    if users:
        raise ConflictError(
            "HAS_DEPENDENTS", "이 부서에 속한 사용자가 있어 삭제할 수 없습니다"
        )
    # 센터는 여전히 FK로 참조하므로 그쪽 위반은 delete_entity가 409로 바꾼다.
    await delete_entity(
        session,
        department,
        message="이 부서를 참조하는 센터·하위 부서가 있어 삭제할 수 없습니다",
    )
