from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.enums import ActivityAction, NotificationType, TripStatus
from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models import ActivityLog, Notification
from app.schemas.trip import RejectRequest
from app.services.trips import (
    approve_trip,
    complete_trip,
    list_timeline,
    reject_trip,
    reopen_trip,
    submit_trip,
)
from tests.factories import make_trip, make_user


async def _pair(db_session):
    manager = await make_user(db_session, name="김연구")
    employee = await make_user(db_session, manager=manager, name="이사원")
    return manager, employee


async def test_submit_assigns_the_managers_approval(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(db_session, user=employee)

    detail = await submit_trip(db_session, user=employee, trip_id=trip.id)

    assert detail.status is TripStatus.SUBMITTED
    assert detail.approver_id == manager.id
    assert detail.submitted_at is not None


async def test_submit_notifies_the_approver(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(db_session, user=employee)

    await submit_trip(db_session, user=employee, trip_id=trip.id)

    notification = (await db_session.execute(select(Notification))).scalar_one()
    assert notification.user_id == manager.id
    assert notification.type is NotificationType.TRIP_SUBMITTED
    assert notification.link_url == f"/trips/{trip.id}"


async def test_submit_requires_a_manager(db_session):
    orphan = await make_user(db_session)
    trip = await make_trip(db_session, user=orphan)

    with pytest.raises(ConflictError) as exc_info:
        await submit_trip(db_session, user=orphan, trip_id=trip.id)

    assert exc_info.value.code == "NO_APPROVER"


async def test_submit_rejects_non_draft(db_session):
    _, employee = await _pair(db_session)
    trip = await make_trip(db_session, user=employee, status=TripStatus.APPROVED)

    with pytest.raises(ConflictError) as exc_info:
        await submit_trip(db_session, user=employee, trip_id=trip.id)

    assert exc_info.value.code == "TRIP_INVALID_TRANSITION"


async def test_submit_clears_the_previous_reject_reason(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session, user=employee, status=TripStatus.DRAFT, reject_reason="예산 초과"
    )

    detail = await submit_trip(db_session, user=employee, trip_id=trip.id)

    assert detail.reject_reason is None


async def test_approve_by_the_assigned_approver(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session, user=employee, status=TripStatus.SUBMITTED, approver_id=manager.id
    )

    detail = await approve_trip(db_session, user=manager, trip_id=trip.id)

    assert detail.status is TripStatus.APPROVED
    assert detail.approved_at is not None
    notification = (await db_session.execute(select(Notification))).scalar_one()
    assert notification.user_id == employee.id
    assert notification.type is NotificationType.TRIP_APPROVED


async def test_approve_by_the_owner_is_forbidden(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session, user=employee, status=TripStatus.SUBMITTED, approver_id=manager.id
    )

    with pytest.raises(ForbiddenError) as exc_info:
        await approve_trip(db_session, user=employee, trip_id=trip.id)

    assert exc_info.value.code == "NOT_TRIP_APPROVER"


async def test_reject_stores_the_reason_and_notifies(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session, user=employee, status=TripStatus.SUBMITTED, approver_id=manager.id
    )

    detail = await reject_trip(
        db_session, user=manager, trip_id=trip.id, payload=RejectRequest(reason="  예산 초과  ")
    )

    assert detail.status is TripStatus.REJECTED
    assert detail.reject_reason == "예산 초과"
    notification = (await db_session.execute(select(Notification))).scalar_one()
    assert notification.user_id == employee.id
    assert notification.type is NotificationType.TRIP_REJECTED
    assert "예산 초과" in notification.body


async def test_reject_requires_a_reason(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session, user=employee, status=TripStatus.SUBMITTED, approver_id=manager.id
    )

    with pytest.raises(ValidationError) as exc_info:
        await reject_trip(
            db_session, user=manager, trip_id=trip.id, payload=RejectRequest(reason="   ")
        )

    assert exc_info.value.code == "REJECT_REASON_REQUIRED"


async def test_reopen_returns_a_rejected_trip_to_draft(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session,
        user=employee,
        status=TripStatus.REJECTED,
        approver_id=manager.id,
        reject_reason="예산 초과",
    )

    detail = await reopen_trip(db_session, user=employee, trip_id=trip.id)

    assert detail.status is TripStatus.DRAFT
    assert detail.approver_id is None
    assert detail.submitted_at is None
    # 무엇을 고쳐야 하는지 화면에서 계속 보여야 하므로 사유는 남긴다.
    assert detail.reject_reason == "예산 초과"


async def test_reopen_rejects_non_rejected_trip(db_session):
    _, employee = await _pair(db_session)
    trip = await make_trip(db_session, user=employee, status=TripStatus.DRAFT)

    with pytest.raises(ConflictError) as exc_info:
        await reopen_trip(db_session, user=employee, trip_id=trip.id)

    assert exc_info.value.code == "TRIP_INVALID_TRANSITION"


async def test_reopen_by_the_approver_is_forbidden(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session, user=employee, status=TripStatus.REJECTED, approver_id=manager.id
    )

    with pytest.raises(ForbiddenError) as exc_info:
        await reopen_trip(db_session, user=manager, trip_id=trip.id)

    assert exc_info.value.code == "NOT_TRIP_OWNER"


async def test_complete_requires_the_trip_to_have_ended(db_session):
    manager, employee = await _pair(db_session)
    future = date.today() + timedelta(days=3)
    trip = await make_trip(
        db_session,
        user=employee,
        status=TripStatus.APPROVED,
        approver_id=manager.id,
        start_date=future,
    )

    with pytest.raises(ConflictError) as exc_info:
        await complete_trip(db_session, user=employee, trip_id=trip.id)

    assert exc_info.value.code == "TRIP_NOT_ENDED"


async def test_complete_after_the_end_date(db_session):
    manager, employee = await _pair(db_session)
    past = date.today() - timedelta(days=10)
    trip = await make_trip(
        db_session,
        user=employee,
        status=TripStatus.APPROVED,
        approver_id=manager.id,
        start_date=past,
    )

    detail = await complete_trip(db_session, user=employee, trip_id=trip.id)

    assert detail.status is TripStatus.COMPLETED
    # 완료는 본인이 본인 출장에 대해 하는 일이라 알릴 상대가 없다.
    assert (await db_session.execute(select(Notification))).scalars().all() == []
    log = (await db_session.execute(select(ActivityLog))).scalar_one()
    assert log.action is ActivityAction.COMPLETED


async def test_complete_by_the_approver_is_forbidden(db_session):
    manager, employee = await _pair(db_session)
    past = date.today() - timedelta(days=10)
    trip = await make_trip(
        db_session,
        user=employee,
        status=TripStatus.APPROVED,
        approver_id=manager.id,
        start_date=past,
    )

    with pytest.raises(ForbiddenError) as exc_info:
        await complete_trip(db_session, user=manager, trip_id=trip.id)

    assert exc_info.value.code == "NOT_TRIP_OWNER"


async def test_a_stranger_cannot_reach_any_transition(db_session):
    """볼 수 없는 출장은 403이 아니라 404다 — 존재 자체를 알려주지 않는다."""
    manager, employee = await _pair(db_session)
    stranger = await make_user(db_session)
    trip = await make_trip(
        db_session, user=employee, status=TripStatus.SUBMITTED, approver_id=manager.id
    )

    with pytest.raises(NotFoundError):
        await approve_trip(db_session, user=stranger, trip_id=trip.id)


async def test_timeline_is_ordered_and_carries_actor_names(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(db_session, user=employee)
    await submit_trip(db_session, user=employee, trip_id=trip.id)
    await approve_trip(db_session, user=manager, trip_id=trip.id)

    entries = await list_timeline(db_session, user=employee, trip_id=trip.id)

    assert [entry.action for entry in entries] == [
        ActivityAction.SUBMITTED,
        ActivityAction.APPROVED,
    ]
    assert [entry.actor_name for entry in entries] == ["이사원", "김연구"]
    assert entries[0].from_status == "DRAFT"
    assert entries[1].to_status == "APPROVED"


async def test_timeline_of_someone_elses_trip_is_404(db_session):
    _, employee = await _pair(db_session)
    stranger = await make_user(db_session)
    trip = await make_trip(db_session, user=employee)

    with pytest.raises(NotFoundError) as exc_info:
        await list_timeline(db_session, user=stranger, trip_id=trip.id)

    assert exc_info.value.status_code == 404


async def test_full_reject_reopen_resubmit_cycle(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(db_session, user=employee)

    await submit_trip(db_session, user=employee, trip_id=trip.id)
    await reject_trip(
        db_session, user=manager, trip_id=trip.id, payload=RejectRequest(reason="예산 초과")
    )
    await reopen_trip(db_session, user=employee, trip_id=trip.id)
    detail = await submit_trip(db_session, user=employee, trip_id=trip.id)

    assert detail.status is TripStatus.SUBMITTED
    assert detail.reject_reason is None
    assert detail.approver_id == manager.id
