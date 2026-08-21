from fastapi import APIRouter, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser, DbSession
from app.enums import UserStatus
from app.errors import AuthError
from app.models import Department, User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    PublicDepartment,
    SignupRequest,
    SignupResponse,
    UserOut,
)
from app.security import create_access_token, hash_password, verify_password
from app.services import signup as signup_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# 존재하지 않는 계정에도 bcrypt를 태우기 위한 더미 해시. 모듈 로드 시 한 번만 계산한다.
_DUMMY_PASSWORD_HASH = hash_password("skon-login-timing-equalizer")


async def _to_user_out(session: AsyncSession, user: User) -> UserOut:
    department = await session.get(Department, user.department_id)
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        employee_no=user.employee_no,
        position_code=user.position_code,
        role=user.role,
        department_id=user.department_id,
        department_name=department.name if department else "",
        manager_id=user.manager_id,
    )


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, session: DbSession) -> LoginResponse:
    user = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    # 사용자가 없거나 비활성이어도 bcrypt 검증을 항상 수행한다. 건너뛰면 응답 시간으로
    # 계정 존재 여부가 새어나가, 위에서 에러 코드를 통일한 의미가 사라진다.
    stored_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(payload.password, stored_hash)
    if user is None or not password_ok:
        raise AuthError("INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다")

    # 여기서부터는 비밀번호를 맞힌 사람이다. 그에게만 가입 상태를 알린다 — 상태를 비밀번호
    # 검증 **앞에서** 보면 이메일만으로 계정 존재가 드러난다. 순서가 방어의 전부다.
    if user.status is UserStatus.PENDING:
        raise AuthError("PENDING_APPROVAL", "관리자 승인 대기 중입니다")
    if user.status is UserStatus.REJECTED:
        raise AuthError("SIGNUP_REJECTED", "가입이 거절되었습니다. 관리자에게 문의하십시오")
    if not user.is_active:
        # 승인됐지만 관리자가 정지시킨 계정. 이유를 알릴 근거가 없으므로 기존 메시지다.
        raise AuthError("INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다")

    return LoginResponse(
        access_token=create_access_token(user_id=user.id),
        user=await _to_user_out(session, user),
    )


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser, session: DbSession) -> UserOut:
    return await _to_user_out(session, user)


@router.get("/departments", response_model=list[PublicDepartment])
async def public_departments(session: DbSession) -> list[PublicDepartment]:
    """**미인증.** 가입 폼의 부서 드롭다운용으로 id·name만 낸다.

    `get_principal`을 지나지 않으므로 `SCOPE_REQUIREMENTS`에 넣지 않는다 — 소진 가드는
    인증 라우트만 대조한다.
    """
    return await signup_service.list_public_departments(session)


@router.post(
    "/signup", response_model=SignupResponse, status_code=http_status.HTTP_201_CREATED
)
async def signup(payload: SignupRequest, session: DbSession) -> SignupResponse:
    """**미인증.** 가입 신청만 만든다. 승인 전에는 로그인할 수 없으므로 토큰을 주지 않는다."""
    return await signup_service.signup(session, payload=payload)
