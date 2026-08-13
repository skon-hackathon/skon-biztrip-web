from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import UserRole
from app.models.base import Base, TimestampMixin


class Department(Base, TimestampMixin):
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("department.id"))


# 주의: "user"는 PostgreSQL 예약어(현재 세션 역할명을 뜻하는 의사 상수)이므로 raw SQL에서는
# 반드시 큰따옴표로 감싸 SELECT * FROM "user" 처럼 써야 한다. SQLAlchemy ORM/Core는 자동으로
# 따옴표를 붙이지만, 따옴표 없는 raw SQL은 조용히 다른 값(연결 계정명)을 반환한다.
class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    employee_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("department.id"), nullable=False)
    position_code: Mapped[str] = mapped_column(String(30), nullable=False)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"), default=UserRole.EMPLOYEE, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
