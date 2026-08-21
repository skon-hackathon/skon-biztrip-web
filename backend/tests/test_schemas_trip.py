from datetime import date

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
    }
    payload.update(overrides)
    return payload


def test_trip_create_parses_dates():
    payload = TripCreate.model_validate(_create_payload())

    assert payload.start_date == date(2026, 9, 1)
    assert payload.end_date == date(2026, 9, 3)


def test_trip_create_rejects_blank_title():
    with pytest.raises(PydanticValidationError):
        TripCreate.model_validate(_create_payload(title=""))


@pytest.mark.parametrize(
    "field_name",
    ["transport_code", "accommodation_code", "cost_center_code", "estimated_cost"],
)
def test_trip_write_schemas_dropped_fields(field_name):
    """출장 신청에서 뺀 필드가 되살아나지 않게 잠근다. 되살아나면 화면에 없는 값을
    API가 요구하게 되고, 코스트센터는 정산 화면이 고르기로 한 결정이 무효가 된다."""
    assert field_name not in TripCreate.model_fields
    assert field_name not in TripUpdate.model_fields


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
