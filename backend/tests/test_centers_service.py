import pytest

from app.errors import ValidationError
from app.models import CostCenter, FundCenter
from app.services.centers import assert_cost_center, load_active_center_codes
from tests.factories import make_cost_center, make_fund_center


async def test_load_active_center_codes_returns_only_active(db_session):
    await make_cost_center(db_session, "CC9001")
    await make_cost_center(db_session, "CC9002", is_active=False)

    codes = await load_active_center_codes(db_session, CostCenter)

    assert codes == {"CC9001"}


async def test_load_active_center_codes_is_per_model(db_session):
    await make_cost_center(db_session, "CC9001")
    await make_fund_center(db_session, "FC9001")

    assert await load_active_center_codes(db_session, FundCenter) == {"FC9001"}


async def test_assert_cost_center_accepts_active_code(db_session):
    await make_cost_center(db_session, "CC9001")

    await assert_cost_center(db_session, "CC9001")


async def test_assert_cost_center_rejects_inactive_code(db_session):
    await make_cost_center(db_session, "CC9002", is_active=False)

    with pytest.raises(ValidationError) as exc_info:
        await assert_cost_center(db_session, "CC9002")

    error = exc_info.value
    assert error.status_code == 400
    assert error.code == "INVALID_COST_CENTER"
    assert error.field == "cost_center_code"


async def test_assert_cost_center_rejects_unknown_code(db_session):
    await make_cost_center(db_session, "CC9001")

    with pytest.raises(ValidationError) as exc_info:
        await assert_cost_center(db_session, "CC9999")

    error = exc_info.value
    assert error.code == "INVALID_COST_CENTER"
    assert error.field == "cost_center_code"


async def test_assert_cost_center_rejects_none(db_session):
    with pytest.raises(ValidationError) as exc_info:
        await assert_cost_center(db_session, None)

    assert exc_info.value.code == "INVALID_COST_CENTER"


async def test_assert_cost_center_reports_custom_field(db_session):
    with pytest.raises(ValidationError) as exc_info:
        await assert_cost_center(db_session, "CC9999", field="trip.cost_center_code")

    assert exc_info.value.field == "trip.cost_center_code"
