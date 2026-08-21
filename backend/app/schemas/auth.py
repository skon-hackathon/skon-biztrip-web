from pydantic import BaseModel, EmailStr, Field, field_validator

from app.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        """이메일을 소문자로 고정한다.

        Postgres의 `=`도 unique 인덱스도 대소문자를 구분하고, Pydantic의 EmailStr은
        도메인만 소문자화한다. 정규화하지 않으면 대소문자만 다른 같은 주소가 서로
        다른 계정이 되어 가입 중복 가드가 통째로 우회된다. 로그인에도 같은 정규화를
        걸어야 대문자로 가입한 사람이 자기 계정에 들어갈 수 있다.
        """
        return value.lower()


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    # ACTIVE 계정만 토큰을 얻을 수 있고, 승인이 이 두 값을 강제하므로
    # 로그인·/auth/me 응답에서는 항상 값이 있다. 모델은 nullable이지만
    # 여기서 str로 두는 것이 프론트 계약을 좁게 유지한다.
    employee_no: str
    position_code: str
    role: UserRole
    department_id: int
    department_name: str
    manager_id: int | None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SignupRequest(BaseModel):
    email: EmailStr
    # 길이는 서비스의 assert_password_length가 본다. max_length는 **문자 수**라
    # 한글 72자(216바이트)를 통과시켜 bcrypt에서 터진다.
    password: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=50)
    department_id: int

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        """이메일을 소문자로 고정한다. LoginRequest의 동명 검증기와 이유가 같다."""
        return value.lower()


class SignupResponse(BaseModel):
    """토큰을 넣지 않는다. 승인 전에는 로그인할 수 없으므로 토큰을 주면 거짓말이 된다."""

    email: str
    status: str
    message: str


class PublicDepartment(BaseModel):
    """미인증 가입 폼의 부서 드롭다운용. id·name만 낸다."""

    id: int
    name: str
