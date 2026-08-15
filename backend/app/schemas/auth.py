from pydantic import BaseModel, EmailStr

from app.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
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
