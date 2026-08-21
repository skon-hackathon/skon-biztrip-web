"""PATCH 스키마는 '미지정'과 'null로 지우기'를 구분해야 한다 — exclude_unset이 그 수단이다."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.enums import UserRole
from app.schemas.admin import (
    AdminUserCreate,
    CenterUpdate,
    CodeCreate,
    DepartmentCreate,
    DepartmentUpdate,
)


def test_department_update_omits_unset_fields():
    payload = DepartmentUpdate.model_validate({"name": "새이름"})
    assert payload.model_dump(exclude_unset=True) == {"name": "새이름"}


def test_department_update_keeps_an_explicit_null_parent():
    payload = DepartmentUpdate.model_validate({"parent_id": None})
    assert payload.model_dump(exclude_unset=True) == {"parent_id": None}


def test_center_update_keeps_an_explicit_false():
    payload = CenterUpdate.model_validate({"is_active": False})
    assert payload.model_dump(exclude_unset=True) == {"is_active": False}


def test_department_code_cannot_be_empty():
    with pytest.raises(PydanticValidationError):
        DepartmentCreate.model_validate({"code": "", "name": "부서"})


def test_code_create_defaults_extra_to_an_empty_dict():
    payload = CodeCreate.model_validate({"code": "AIR", "name": "항공"})
    assert payload.extra == {}
    assert payload.sort_order == 0
    assert payload.is_active is True


def test_admin_user_create_defaults_to_employee():
    payload = AdminUserCreate.model_validate(
        {
            "email": "new@skon.example",
            "password": "skon1234!",
            "name": "신입",
            "employee_no": "E9999",
            "department_id": 1,
            "position_code": "STAFF",
        }
    )
    assert payload.role is UserRole.EMPLOYEE
    assert payload.is_active is True
    assert payload.manager_id is None


def test_admin_user_out_allows_null_employee_no():
    from app.enums import UserRole, UserStatus
    from app.schemas.admin import AdminUserOut

    out = AdminUserOut(
        id=1,
        email="a@b.com",
        name="가입자",
        employee_no=None,
        department_id=1,
        department_name="부서",
        position_code=None,
        manager_id=None,
        manager_name=None,
        role=UserRole.EMPLOYEE,
        status=UserStatus.PENDING,
        is_active=False,
    )
    assert out.employee_no is None
    assert out.status is UserStatus.PENDING


def test_admin_user_update_has_no_status_field():
    # status는 전이 엔드포인트만 바꾼다. PATCH로 바꿀 수 있으면 전이 가드를
    # 우회하는 두 번째 경로가 생긴다.
    from app.schemas.admin import AdminUserUpdate

    assert "status" not in AdminUserUpdate.model_fields


def test_user_approve_requires_employee_no_and_position():
    import pytest
    from pydantic import ValidationError as PydanticValidationError

    from app.schemas.admin import UserApprove

    with pytest.raises(PydanticValidationError):
        UserApprove(position_code="STAFF")
    with pytest.raises(PydanticValidationError):
        UserApprove(employee_no="E0100")

    approved = UserApprove(employee_no="E0100", position_code="STAFF")
    assert approved.manager_id is None
    assert approved.role.value == "EMPLOYEE"
