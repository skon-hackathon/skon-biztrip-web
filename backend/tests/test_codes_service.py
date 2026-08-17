import pytest
from sqlalchemy import event

from app.errors import ValidationError
from app.models import Code, CodeGroup
from app.services.codes import assert_valid_code, load_active_codes, validate_codes
from tests.factories import make_code_group


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


async def test_validate_codes_accepts_all_valid_values(db_session):
    await make_code_group(db_session, "TRANSPORT", ["AIR", "RAIL"])
    await make_code_group(db_session, "ACCOMMODATION", ["HOTEL"])

    await validate_codes(
        db_session,
        [
            ("TRANSPORT", "transport_code", "AIR"),
            ("ACCOMMODATION", "accommodation_code", "HOTEL"),
        ],
    )


async def test_validate_codes_reports_the_offending_field(db_session):
    await make_code_group(db_session, "TRANSPORT", ["AIR", "RAIL"])
    await make_code_group(db_session, "ACCOMMODATION", ["HOTEL"])

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(
            db_session,
            [
                ("TRANSPORT", "transport_code", "AIR"),
                ("ACCOMMODATION", "accommodation_code", "IGLOO"),
            ],
        )

    error = exc_info.value
    assert error.code == "INVALID_CODE"
    assert error.field == "accommodation_code"
    assert "ACCOMMODATION" in error.message


async def test_validate_codes_reports_the_first_failure_in_spec_order(db_session):
    await make_code_group(db_session, "TRANSPORT", ["AIR"])
    await make_code_group(db_session, "ACCOMMODATION", ["HOTEL"])

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(
            db_session,
            [
                ("TRANSPORT", "transport_code", "ROCKET"),
                ("ACCOMMODATION", "accommodation_code", "IGLOO"),
            ],
        )

    assert exc_info.value.field == "transport_code"


async def test_validate_codes_raises_for_unknown_group(db_session):
    await make_code_group(db_session, "TRANSPORT", ["AIR"])

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(
            db_session,
            [("TRANSPORT", "transport_code", "AIR"), ("NOPE", "nope_code", "X")],
        )

    error = exc_info.value
    assert error.code == "UNKNOWN_CODE_GROUP"
    assert error.field == "nope_code"


async def test_validate_codes_raises_for_inactive_group(db_session):
    await make_code_group(db_session, "RETIRED", ["AIR"], is_active=False)

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(db_session, [("RETIRED", "transport_code", "AIR")])

    error = exc_info.value
    assert error.code == "UNKNOWN_CODE_GROUP"
    assert error.field == "transport_code"


async def test_validate_codes_rejects_inactive_code_value(db_session):
    group = await make_code_group(db_session, "TRANSPORT", ["AIR"])
    db_session.add(Code(group_id=group.id, code="SHIP", name="선박", sort_order=2, is_active=False))
    await db_session.flush()

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(db_session, [("TRANSPORT", "transport_code", "SHIP")])

    error = exc_info.value
    assert error.code == "INVALID_CODE"
    assert error.field == "transport_code"


async def test_validate_codes_reports_group_failures_before_value_failures(db_session):
    await make_code_group(db_session, "TRANSPORT", ["AIR"])

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(
            db_session,
            [
                ("TRANSPORT", "transport_code", "ROCKET"),
                ("NOPE", "nope_code", "X"),
            ],
        )

    error = exc_info.value
    assert error.code == "UNKNOWN_CODE_GROUP"
    assert error.field == "nope_code"


async def test_validate_codes_treats_group_with_no_active_codes_as_invalid_value(db_session):
    await make_code_group(db_session, "EMPTY_GROUP", [])

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(db_session, [("EMPTY_GROUP", "some_code", "X")])

    assert exc_info.value.code == "INVALID_CODE"


async def test_validate_codes_issues_two_queries_regardless_of_group_count(db_session):
    await make_code_group(db_session, "TRANSPORT", ["AIR"])
    await make_code_group(db_session, "ACCOMMODATION", ["HOTEL"])
    await make_code_group(db_session, "COUNTRY", ["KR"])

    counter = {"n": 0}

    @event.listens_for(db_session.sync_session, "do_orm_execute")
    def _count(_context) -> None:
        counter["n"] += 1

    await validate_codes(
        db_session,
        [
            ("TRANSPORT", "transport_code", "AIR"),
            ("ACCOMMODATION", "accommodation_code", "HOTEL"),
            ("COUNTRY", "country_code", "KR"),
        ],
    )

    assert counter["n"] == 2
