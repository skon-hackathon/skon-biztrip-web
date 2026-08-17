from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.enums import TripStatus
from app.schemas.common import Page
from app.schemas.trip import TripCreate, TripListItem, TripUpdate


def _create_payload(**overrides) -> dict:
    payload = {
        "title": "울산공장 품질점검",
        "purpose_code": "AUDIT",
        "purpose_detail": "라인 3 품질 이슈 현장 확인",
        "destination_type_code": "DOMESTIC",
        "country_code": "KR",
        "city": "울산",
        "start_date": "2026-09-01",
        "end_date": "2026-09-03",
        "transport_code": "RAIL",
        "accommodation_code": "HOTEL",
        "cost_center_code": "CC2030",
        "estimated_cost": "450000",
    }
    payload.update(overrides)
    return payload


def test_trip_create_parses_dates_and_decimal():
    payload = TripCreate.model_validate(_create_payload())

    assert payload.start_date == date(2026, 9, 1)
    assert payload.estimated_cost == Decimal("450000")


def test_trip_create_rejects_blank_title():
    with pytest.raises(PydanticValidationError):
        TripCreate.model_validate(_create_payload(title=""))


def test_trip_create_does_not_constrain_amounts():
    """금액 제약은 trip_rules.py가 400 + 도메인 코드로 낸다. 여기서 422로 잡히면
    Agent가 보는 에러 코드가 필드마다 달라진다."""
    negative = TripCreate.model_validate(_create_payload(estimated_cost="-1"))
    huge = TripCreate.model_validate(_create_payload(estimated_cost="9" * 30))

    assert negative.estimated_cost == Decimal("-1")
    assert huge.estimated_cost == Decimal("9" * 30)


def test_trip_create_does_not_constrain_date_order():
    payload = TripCreate.model_validate(
        _create_payload(start_date="2026-09-05", end_date="2026-09-01")
    )

    assert payload.end_date < payload.start_date


def test_trip_update_tracks_which_fields_were_sent():
    payload = TripUpdate.model_validate({"city": "서산"})

    assert payload.model_dump(exclude_unset=True) == {"city": "서산"}


def test_trip_update_allows_empty_body():
    assert TripUpdate.model_validate({}).model_dump(exclude_unset=True) == {}


def test_page_is_generic_over_the_item_type():
    page = Page[TripListItem](
        items=[
            TripListItem(
                id=1,
                trip_no="BT-2026-0001",
                title="울산공장 품질점검",
                city="울산",
                country_code="KR",
                destination_type_code="DOMESTIC",
                purpose_code="AUDIT",
                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 3),
                status=TripStatus.DRAFT,
                estimated_cost=Decimal("450000"),
                user_id=1,
                user_name="박출장",
                approver_id=None,
                approver_name=None,
            )
        ],
        total=1,
        page=1,
        size=20,
    )

    assert page.items[0].trip_no == "BT-2026-0001"
    assert page.model_dump()["total"] == 1
