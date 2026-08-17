from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.deps import CurrentUser, DbSession
from app.enums import TripStatus
from app.schemas.common import Page
from app.schemas.trip import (
    RejectRequest,
    TimelineEntry,
    TripCreate,
    TripDetail,
    TripListItem,
    TripUpdate,
)
from app.services import trips as trip_service

router = APIRouter(prefix="/api/v1/trips", tags=["trips"])


@router.get("", response_model=Page[TripListItem])
async def list_trips(
    user: CurrentUser,
    session: DbSession,
    scope: Annotated[Literal["mine", "approvals", "all"], Query()] = "mine",
    # 파라미터 이름을 status로 두면 fastapi.status 모듈과 충돌한다. 쿼리스트링은
    # 그대로 ?status=APPROVED 다.
    status_: Annotated[list[TripStatus] | None, Query(alias="status")] = None,
    destination_type_code: str | None = None,
    country_code: str | None = None,
    q: str | None = None,
    start_date_from: date | None = None,
    start_date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[TripListItem]:
    return await trip_service.list_trips(
        session,
        user=user,
        filters=trip_service.TripFilters(
            scope=scope,
            status=status_ or [],
            destination_type_code=destination_type_code,
            country_code=country_code,
            q=q,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            page=page,
            size=size,
        ),
    )


@router.post("", response_model=TripDetail, status_code=status.HTTP_201_CREATED)
async def create_trip(payload: TripCreate, user: CurrentUser, session: DbSession) -> TripDetail:
    return await trip_service.create_trip(session, user=user, payload=payload)


@router.get("/{trip_id}", response_model=TripDetail)
async def get_trip(trip_id: int, user: CurrentUser, session: DbSession) -> TripDetail:
    return await trip_service.get_trip(session, user=user, trip_id=trip_id)


@router.patch("/{trip_id}", response_model=TripDetail)
async def update_trip(
    trip_id: int, payload: TripUpdate, user: CurrentUser, session: DbSession
) -> TripDetail:
    return await trip_service.update_trip(session, user=user, trip_id=trip_id, payload=payload)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip(trip_id: int, user: CurrentUser, session: DbSession) -> None:
    await trip_service.delete_trip(session, user=user, trip_id=trip_id)


@router.post("/{trip_id}/submit", response_model=TripDetail)
async def submit_trip(trip_id: int, user: CurrentUser, session: DbSession) -> TripDetail:
    return await trip_service.submit_trip(session, user=user, trip_id=trip_id)


@router.post("/{trip_id}/approve", response_model=TripDetail)
async def approve_trip(trip_id: int, user: CurrentUser, session: DbSession) -> TripDetail:
    return await trip_service.approve_trip(session, user=user, trip_id=trip_id)


@router.post("/{trip_id}/reject", response_model=TripDetail)
async def reject_trip(
    trip_id: int, payload: RejectRequest, user: CurrentUser, session: DbSession
) -> TripDetail:
    return await trip_service.reject_trip(session, user=user, trip_id=trip_id, payload=payload)


@router.post("/{trip_id}/reopen", response_model=TripDetail)
async def reopen_trip(trip_id: int, user: CurrentUser, session: DbSession) -> TripDetail:
    return await trip_service.reopen_trip(session, user=user, trip_id=trip_id)


@router.post("/{trip_id}/complete", response_model=TripDetail)
async def complete_trip(trip_id: int, user: CurrentUser, session: DbSession) -> TripDetail:
    return await trip_service.complete_trip(session, user=user, trip_id=trip_id)


@router.get("/{trip_id}/timeline", response_model=list[TimelineEntry])
async def get_timeline(trip_id: int, user: CurrentUser, session: DbSession) -> list[TimelineEntry]:
    return await trip_service.list_timeline(session, user=user, trip_id=trip_id)
