"""사용자 마스터 CRUD.

삭제 엔드포인트가 없는 이유: `user.id`는 trip·expense_report·corporate_card·api_key·
activity_log가 참조한다. 삭제는 사실상 항상 409이고, 감사 흔적을 지우는 것도 옳지 않다.
비활성화(`is_active=false`)가 유일한 종료 경로이며 로그인이 즉시 막힌다.

이름 해석(부서명·결재자명)은 행마다 조회하지 않는다. `id.in_(...)` 일괄 조회 2번으로
끝내며, 그 사실을 쿼리 수 테스트가 고정한다.
"""

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import UserRole
from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import Department, User
from app.schemas.admin import AdminUserCreate, AdminUserOut, AdminUserUpdate, PasswordSet
from app.schemas.common import Page
from app.security import hash_password
from app.services.admin.common import assert_password_length, assert_unique
from app.services.codes import validate_codes

#: 직급은 공통코드 POSITION 그룹에서만 나온다. 모든 쓰기 경로가 이 검증을 지난다.
_POSITION_GROUP = "POSITION"


@dataclass(frozen=True)
class UserFilters:
    q: str | None = None
    department_id: int | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    page: int = 1
    size: int = 20


async def _to_out(session: AsyncSession, users: list[User]) -> list[AdminUserOut]:
    department_ids = {user.department_id for user in users}
    manager_ids = {user.manager_id for user in users if user.manager_id is not None}

    department_names: dict[int, str] = {}
    if department_ids:
        rows = await session.execute(
            select(Department.id, Department.name).where(Department.id.in_(department_ids))
        )
        department_names = {row[0]: row[1] for row in rows}

    manager_names: dict[int, str] = {}
    if manager_ids:
        rows = await session.execute(select(User.id, User.name).where(User.id.in_(manager_ids)))
        manager_names = {row[0]: row[1] for row in rows}

    return [
        AdminUserOut(
            id=user.id,
            email=user.email,
            name=user.name,
            employee_no=user.employee_no,
            department_id=user.department_id,
            department_name=department_names.get(user.department_id, ""),
            position_code=user.position_code,
            manager_id=user.manager_id,
            manager_name=manager_names.get(user.manager_id) if user.manager_id else None,
            role=user.role,
            is_active=user.is_active,
        )
        for user in users
    ]


async def list_users(session: AsyncSession, *, filters: UserFilters) -> Page[AdminUserOut]:
    conditions = []
    if filters.q:
        # 출장 목록의 q와 같은 판단: LIKE 와일드카드를 이스케이프하지 않는다(데모 범위).
        pattern = f"%{filters.q}%"
        conditions.append(
            or_(
                User.name.ilike(pattern),
                User.email.ilike(pattern),
                User.employee_no.ilike(pattern),
            )
        )
    if filters.department_id is not None:
        conditions.append(User.department_id == filters.department_id)
    if filters.role is not None:
        conditions.append(User.role == filters.role)
    if filters.is_active is not None:
        conditions.append(User.is_active.is_(filters.is_active))

    total = await session.scalar(select(func.count()).select_from(User).where(*conditions))
    rows = (
        (
            await session.execute(
                select(User)
                .where(*conditions)
                .order_by(User.employee_no)
                .offset((filters.page - 1) * filters.size)
                .limit(filters.size)
            )
        )
        .scalars()
        .all()
    )
    return Page(
        items=await _to_out(session, list(rows)),
        total=total or 0,
        page=filters.page,
        size=filters.size,
    )


async def _load(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("USER_NOT_FOUND", f"존재하지 않는 사용자입니다: {user_id}")
    return user


async def get_user(session: AsyncSession, *, user_id: int) -> AdminUserOut:
    user = await _load(session, user_id)
    return (await _to_out(session, [user]))[0]


async def _assert_department(session: AsyncSession, department_id: int) -> None:
    if await session.get(Department, department_id) is None:
        raise ValidationError(
            "INVALID_DEPARTMENT",
            f"존재하지 않는 부서입니다: {department_id}",
            field="department_id",
        )


async def _assert_manager(
    session: AsyncSession, manager_id: int | None, *, self_id: int | None = None
) -> None:
    if manager_id is None:
        return
    if self_id is not None and manager_id == self_id:
        raise ValidationError(
            "INVALID_MANAGER", "자기 자신을 결재자로 지정할 수 없습니다", field="manager_id"
        )
    if await session.get(User, manager_id) is None:
        raise ValidationError(
            "INVALID_MANAGER", f"존재하지 않는 결재자입니다: {manager_id}", field="manager_id"
        )


async def create_user(session: AsyncSession, *, payload: AdminUserCreate) -> AdminUserOut:
    assert_password_length(payload.password)
    await assert_unique(
        session,
        User.email,
        payload.email,
        code="DUPLICATE_EMAIL",
        message=f"이미 사용 중인 이메일입니다: {payload.email}",
        field="email",
    )
    await assert_unique(
        session,
        User.employee_no,
        payload.employee_no,
        code="DUPLICATE_EMPLOYEE_NO",
        message=f"이미 사용 중인 사번입니다: {payload.employee_no}",
        field="employee_no",
    )
    await _assert_department(session, payload.department_id)
    await _assert_manager(session, payload.manager_id)
    await validate_codes(session, [(_POSITION_GROUP, "position_code", payload.position_code)])

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name,
        employee_no=payload.employee_no,
        department_id=payload.department_id,
        position_code=payload.position_code,
        manager_id=payload.manager_id,
        role=payload.role,
        is_active=payload.is_active,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return (await _to_out(session, [user]))[0]


async def update_user(
    session: AsyncSession, *, actor: User, user_id: int, payload: AdminUserUpdate
) -> AdminUserOut:
    user = await _load(session, user_id)
    changes = payload.model_dump(exclude_unset=True)

    # 자기 자신을 강등·비활성화하면 아무도 Admin 화면에 들어갈 수 없게 될 수 있다.
    # 복구 경로가 DB 직접 수정뿐이므로 막는다.
    if user.id == actor.id:
        if changes.get("role") not in (None, UserRole.ADMIN):
            raise ConflictError(
                "CANNOT_DEMOTE_SELF", "자기 자신의 관리자 권한을 내릴 수 없습니다", field="role"
            )
        if changes.get("is_active") is False:
            raise ConflictError(
                "CANNOT_DEMOTE_SELF", "자기 자신을 비활성화할 수 없습니다", field="is_active"
            )

    if "department_id" in changes and changes["department_id"] is not None:
        await _assert_department(session, changes["department_id"])
    if "manager_id" in changes:
        await _assert_manager(session, changes["manager_id"], self_id=user.id)
    if "position_code" in changes and changes["position_code"] is not None:
        await validate_codes(
            session, [(_POSITION_GROUP, "position_code", changes["position_code"])]
        )

    for field, value in changes.items():
        setattr(user, field, value)
    await session.commit()
    await session.refresh(user)
    return (await _to_out(session, [user]))[0]


async def set_password(session: AsyncSession, *, user_id: int, payload: PasswordSet) -> None:
    user = await _load(session, user_id)
    assert_password_length(payload.password)
    user.password_hash = hash_password(payload.password)
    await session.commit()
