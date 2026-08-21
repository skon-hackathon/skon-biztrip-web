"""미인증 가입 경로.

가입은 열되 승인은 관리자가 한다. 가입자는 이메일·이름·비밀번호·부서만 내고,
사번·직급·결재자·역할은 관리자가 승인 시점에 채운다 — 그 값들은 결재선과 정산 귀속의
근거라 본인이 고르면 틀린다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import UserRole, UserStatus
from app.errors import ConflictError
from app.models import Department, User
from app.schemas.auth import PublicDepartment, SignupRequest, SignupResponse
from app.security import hash_password
from app.services.admin.common import assert_department, assert_password_length
from app.services.user_status import SignupActor, assert_signup_transition_allowed

_PENDING_MESSAGE = "가입 신청이 접수되었습니다. 관리자 승인 후 로그인할 수 있습니다."


async def list_public_departments(session: AsyncSession) -> list[PublicDepartment]:
    """미인증 가입 폼의 부서 드롭다운용. id·name만 낸다.

    부서명이 로그인 없이 보이는 것은 의도된 노출이다. 데모 조직도이고, 대안(부서를
    관리자가 승인 시점에 고르게 하기)은 가입자가 자기 소속을 아는데도 못 적게 만든다.
    """
    rows = await session.execute(
        select(Department.id, Department.name).order_by(Department.code)
    )
    return [PublicDepartment(id=row[0], name=row[1]) for row in rows]


async def signup(session: AsyncSession, *, payload: SignupRequest) -> SignupResponse:
    assert_password_length(payload.password)
    await assert_department(session, payload.department_id)

    existing = await session.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        return await _resubmit(session, existing=existing, payload=payload)

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name,
        employee_no=None,
        department_id=payload.department_id,
        position_code=None,
        manager_id=None,
        role=UserRole.EMPLOYEE,
        status=UserStatus.PENDING,
        # 불변식: status != ACTIVE 이면 is_active = false.
        is_active=False,
    )
    session.add(user)
    await session.commit()
    return SignupResponse(
        email=user.email, status=UserStatus.PENDING.value, message=_PENDING_MESSAGE
    )


async def _resubmit(
    session: AsyncSession, *, existing: User, payload: SignupRequest
) -> SignupResponse:
    """이미 있는 이메일의 분기.

    PENDING을 덮어쓰지 않는 것이 중요하다. 덮어쓰기를 허용하면 남이 신청해 둔 대기 계정에
    내가 아는 비밀번호를 덮어씌운 뒤 승인을 기다려 **계정을 가로챌 수 있다.**
    REJECTED는 이미 관리자가 거부한 행이라 같은 위험이 없다.
    """
    if existing.status is UserStatus.PENDING:
        raise ConflictError(
            "ALREADY_PENDING", "이미 승인 대기 중인 이메일입니다", field="email"
        )
    if existing.status is UserStatus.ACTIVE:
        raise ConflictError(
            "DUPLICATE_EMAIL", f"이미 사용 중인 이메일입니다: {payload.email}", field="email"
        )

    # REJECTED -> PENDING. 전이 가드는 하나만 통과한다.
    assert_signup_transition_allowed(
        existing.status, UserStatus.PENDING, actor=SignupActor.APPLICANT
    )
    existing.name = payload.name
    existing.department_id = payload.department_id
    existing.password_hash = hash_password(payload.password)
    existing.status = UserStatus.PENDING
    existing.is_active = False
    await session.commit()
    return SignupResponse(
        email=existing.email, status=UserStatus.PENDING.value, message=_PENDING_MESSAGE
    )
