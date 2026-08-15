from fastapi import APIRouter
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.errors import AuthError
from app.models import Department, User
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


async def _to_user_out(session, user: User) -> UserOut:
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
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise AuthError("INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다")

    return LoginResponse(
        access_token=create_access_token(user_id=user.id),
        user=await _to_user_out(session, user),
    )


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser, session: DbSession) -> UserOut:
    return await _to_user_out(session, user)
