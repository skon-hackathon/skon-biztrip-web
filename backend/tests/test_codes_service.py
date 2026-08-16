import pytest

from app.errors import ValidationError
from app.models import Code, CodeGroup
from app.services.codes import assert_valid_code, load_active_codes


def test_assert_valid_code_accepts_known_value():
    assert_valid_code("TRANSPORT", "AIR", {"AIR", "RAIL"}, field="transport_code")


def test_assert_valid_code_rejects_unknown_value():
    with pytest.raises(ValidationError) as exc_info:
        assert_valid_code("TRANSPORT", "ROCKET", {"AIR", "RAIL"}, field="transport_code")

    error = exc_info.value
    assert error.status_code == 400
    assert error.code == "INVALID_CODE"
    assert error.field == "transport_code"
    assert "TRANSPORT" in error.message


def test_assert_valid_code_rejects_none():
    with pytest.raises(ValidationError) as exc_info:
        assert_valid_code("TRANSPORT", None, {"AIR"}, field="transport_code")

    assert exc_info.value.code == "INVALID_CODE"


async def test_load_active_codes_returns_only_active(db_session):
    group = CodeGroup(group_code="TRANSPORT", name="이동수단")
    db_session.add(group)
    await db_session.flush()
    db_session.add(Code(group_id=group.id, code="AIR", name="항공", sort_order=1))
    db_session.add(Code(group_id=group.id, code="SHIP", name="선박", sort_order=2, is_active=False))
    await db_session.flush()

    values = await load_active_codes(db_session, "TRANSPORT")

    assert values == {"AIR"}


async def test_load_active_codes_raises_for_unknown_group(db_session):
    with pytest.raises(ValidationError) as exc_info:
        await load_active_codes(db_session, "NOPE")

    assert exc_info.value.code == "UNKNOWN_CODE_GROUP"


async def test_load_active_codes_raises_for_inactive_group(db_session):
    group = CodeGroup(group_code="RETIRED", name="폐지된 그룹", is_active=False)
    db_session.add(group)
    await db_session.flush()
    db_session.add(Code(group_id=group.id, code="AIR", name="항공", sort_order=1))
    await db_session.flush()

    with pytest.raises(ValidationError) as exc_info:
        await load_active_codes(db_session, "RETIRED")

    assert exc_info.value.code == "UNKNOWN_CODE_GROUP"
