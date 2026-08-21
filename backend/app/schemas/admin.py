"""Admin CRUD의 요청·응답 스키마.

`/codes`·`/fund-centers`가 쓰는 스키마와 나눠 둔 이유: 일반 화면은 **활성 값만** 봐야 하고
관리 화면은 **비활성 값도** 봐야 한다. 한 스키마를 두 독자가 공유하면 언젠가 비활성 코드가
출장 신청 드롭다운에 나타난다.

PATCH 스키마의 필드는 전부 Optional이며 서비스가 `model_dump(exclude_unset=True)`로 읽는다 —
`parent_id=None`이 "안 보냄"인지 "null로 지우기"인지는 그 방법으로만 구분된다.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.enums import UserRole, UserStatus

# --- 부서 -------------------------------------------------------------------


class DepartmentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    parent_id: int | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: int | None = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    parent_id: int | None


# --- 공통코드 ---------------------------------------------------------------


class CodeGroupCreate(BaseModel):
    group_code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class CodeGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class CodeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    is_active: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)


class CodeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None
    is_active: bool | None = None
    extra: dict[str, Any] | None = None


class AdminCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    sort_order: int
    is_active: bool
    extra: dict[str, Any]


class AdminCodeGroupOut(BaseModel):
    id: int
    group_code: str
    name: str
    description: str | None
    is_active: bool
    codes: list[AdminCodeOut]


# --- FC / CC ----------------------------------------------------------------


class CenterCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    department_id: int | None = None
    is_active: bool = True


class CenterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    department_id: int | None = None
    is_active: bool | None = None


class AdminCenterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    department_id: int | None
    is_active: bool


# --- 사용자 -----------------------------------------------------------------


class AdminUserCreate(BaseModel):
    email: EmailStr
    # 길이는 서비스의 assert_password_length가 본다. max_length는 **문자 수**라
    # 한글 72자(216바이트)를 통과시켜 bcrypt에서 터진다.
    password: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=50)
    employee_no: str = Field(min_length=1, max_length=20)
    department_id: int
    position_code: str = Field(min_length=1, max_length=30)
    manager_id: int | None = None
    role: UserRole = UserRole.EMPLOYEE
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    department_id: int | None = None
    position_code: str | None = Field(default=None, min_length=1, max_length=30)
    manager_id: int | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserApprove(BaseModel):
    """가입 승인 시 관리자가 채우는 조직 정보.

    전부 필수다(manager_id 제외). 이 값들이 있어야 ACTIVE가 될 수 있고,
    그 강제가 컬럼 NOT NULL 대신 여기와 서비스에 있다.
    """

    employee_no: str = Field(min_length=1, max_length=20)
    position_code: str = Field(min_length=1, max_length=30)
    manager_id: int | None = None
    role: UserRole = UserRole.EMPLOYEE


class PasswordSet(BaseModel):
    password: str = Field(min_length=1)


class AdminUserOut(BaseModel):
    id: int
    email: str
    name: str
    # 가입 대기 계정은 아직 값이 없다. 승인이 값을 채운다.
    employee_no: str | None
    department_id: int
    department_name: str
    position_code: str | None
    manager_id: int | None
    manager_name: str | None
    role: UserRole
    status: UserStatus
    is_active: bool


# --- 법인카드 ---------------------------------------------------------------


class AdminCardCreate(BaseModel):
    user_id: int
    card_no_masked: str = Field(min_length=1, max_length=30)
    brand: str = Field(min_length=1, max_length=30)
    is_active: bool = True


class AdminCardUpdate(BaseModel):
    card_no_masked: str | None = Field(default=None, min_length=1, max_length=30)
    brand: str | None = Field(default=None, min_length=1, max_length=30)
    is_active: bool | None = None


class AdminCardOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    card_no_masked: str
    brand: str
    is_active: bool
