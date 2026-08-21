"""Admin CRUD가 공유하는 가드. 여기가 뚫리면 삭제는 500, 비밀번호는 500이 된다."""

import pytest

from app.errors import ConflictError, ValidationError
from app.models import Department
from app.services.admin.common import (
    assert_password_length,
    assert_unique,
    delete_entity,
)
from tests.factories import make_department


def test_eight_character_ascii_password_passes():
    assert assert_password_length("abcd1234") is None


def test_short_password_is_rejected_with_a_field():
    with pytest.raises(ValidationError) as exc:
        assert_password_length("abc123")
    assert exc.value.code == "PASSWORD_TOO_SHORT"
    assert exc.value.field == "password"


def test_korean_password_of_exactly_72_bytes_passes():
    # 한글 1자 = UTF-8 3바이트. 24자 = 72바이트 = 경계값.
    assert assert_password_length("가" * 24) is None


def test_korean_password_over_72_bytes_is_rejected():
    # 25자 = 75바이트. bcrypt 5.x는 자르지 않고 예외를 던지므로 여기서 막지 않으면 500이다.
    with pytest.raises(ValidationError) as exc:
        assert_password_length("가" * 25)
    assert exc.value.code == "PASSWORD_TOO_LONG"
    assert exc.value.field == "password"


async def test_delete_entity_turns_a_reference_into_409(db_session):
    # FK가 실제로 걸린 참조라야 IntegrityError가 나고, 그 변환이 이 테스트의 대상이다.
    # user.department_id는 계정 공유 때문에 FK가 없으므로 여기 쓸 수 없다 —
    # 그 경로는 services/admin/departments.py가 직접 세고 별도 테스트가 지킨다.
    parent = await make_department(db_session)
    child = await make_department(db_session, name="하위부서")
    child.parent_id = parent.id
    await db_session.flush()

    with pytest.raises(ConflictError) as exc:
        await delete_entity(db_session, parent, message="참조가 있습니다")

    assert exc.value.code == "HAS_DEPENDENTS"
    assert exc.value.status_code == 409


async def test_delete_entity_removes_an_unreferenced_row(db_session):
    department = await make_department(db_session)
    department_id = department.id

    await delete_entity(db_session, department, message="참조가 있습니다")

    assert await db_session.get(Department, department_id) is None


async def test_assert_unique_rejects_an_existing_value(db_session):
    department = await make_department(db_session)

    with pytest.raises(ConflictError) as exc:
        await assert_unique(
            db_session,
            Department.code,
            department.code,
            code="DUPLICATE_DEPARTMENT_CODE",
            message="이미 있는 부서 코드입니다",
            field="code",
        )

    assert exc.value.field == "code"


async def test_assert_unique_allows_a_new_value(db_session):
    assert (
        await assert_unique(
            db_session,
            Department.code,
            "D-NEVER-USED",
            code="DUPLICATE_DEPARTMENT_CODE",
            message="이미 있는 부서 코드입니다",
            field="code",
        )
        is None
    )
