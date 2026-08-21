from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import UserRole
from app.models.base import USER_FK, USER_SCHEMA, Base, TimestampMixin


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
    # 계정을 다른 프로젝트와 공유하려고 이 테이블만 `USER_SCHEMA`(기본 public)에 둔다.
    __table_args__ = {"schema": USER_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    employee_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    # 부서는 이 프로젝트 스키마에 남는다. 공유 테이블이 우리 스키마를 역참조하면 상대
    # 프로젝트가 계정을 만들 때 우리 department 행이 있어야 하므로 FK 제약은 두지 않고,
    # 존재 검증은 서비스가 한다(services/admin/users.py의 _assert_department).
    department_id: Mapped[int] = mapped_column(nullable=False)
    position_code: Mapped[str] = mapped_column(String(30), nullable=False)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey(USER_FK))
    role: Mapped[UserRole] = mapped_column(
        # 공유 테이블이므로 PostgreSQL enum 타입을 쓰지 않는다. 상대 프로젝트가 우리
        # 스키마의 타입을 알아야 하는 결합을 없애려고 varchar로 저장한다. 값은 지금과
        # 같은 멤버명 문자열('EMPLOYEE' 등)이고 검증은 Python Enum이 한다.
        SAEnum(UserRole, name="user_role", native_enum=False, length=20),
        default=UserRole.EMPLOYEE,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
