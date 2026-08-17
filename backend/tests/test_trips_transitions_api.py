from datetime import date, timedelta

from sqlalchemy import select

from app.enums import TripStatus
from app.models import Notification, Trip, User


async def _first_trip(session, status: TripStatus) -> Trip:
    return (
        (await session.execute(select(Trip).where(Trip.status == status).order_by(Trip.id)))
        .scalars()
        .first()
    )


async def _email_of(session, user_id: int) -> str:
    return (await session.get(User, user_id)).email


async def test_submit_moves_draft_to_submitted(client, seeded, login_as):
    trip = await _first_trip(seeded, TripStatus.DRAFT)
    headers = await login_as(await _email_of(seeded, trip.user_id))

    response = await client.post(f"/api/v1/trips/{trip.id}/submit", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUBMITTED"
    assert body["approver_id"] is not None


async def test_submit_twice_returns_409_with_domain_code(client, seeded, login_as):
    trip = await _first_trip(seeded, TripStatus.DRAFT)
    headers = await login_as(await _email_of(seeded, trip.user_id))
    await client.post(f"/api/v1/trips/{trip.id}/submit", headers=headers)

    response = await client.post(f"/api/v1/trips/{trip.id}/submit", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRIP_INVALID_TRANSITION"


async def test_approve_by_the_assigned_manager(client, seeded, login_as):
    trip = await _first_trip(seeded, TripStatus.SUBMITTED)
    headers = await login_as(await _email_of(seeded, trip.approver_id))

    response = await client.post(f"/api/v1/trips/{trip.id}/approve", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"


async def test_approve_by_the_owner_is_403(client, seeded, login_as):
    trip = await _first_trip(seeded, TripStatus.SUBMITTED)
    headers = await login_as(await _email_of(seeded, trip.user_id))

    response = await client.post(f"/api/v1/trips/{trip.id}/approve", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "NOT_TRIP_APPROVER"


async def test_approve_by_an_unrelated_user_is_404(client, seeded, login_as):
    """볼 수 없는 출장은 403이 아니라 404다 — 존재 자체를 알려주지 않는다."""
    trip = await _first_trip(seeded, TripStatus.SUBMITTED)
    owner_email = await _email_of(seeded, trip.user_id)
    stranger = "user1@skon.example" if owner_email != "user1@skon.example" else "user2@skon.example"
    headers = await login_as(stranger)

    response = await client.post(f"/api/v1/trips/{trip.id}/approve", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRIP_NOT_FOUND"


async def test_reject_requires_a_reason(client, seeded, login_as):
    trip = await _first_trip(seeded, TripStatus.SUBMITTED)
    headers = await login_as(await _email_of(seeded, trip.approver_id))

    response = await client.post(
        f"/api/v1/trips/{trip.id}/reject", headers=headers, json={"reason": "  "}
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "REJECT_REASON_REQUIRED"
    assert error["field"] == "reason"


async def test_reject_then_reopen_then_resubmit(client, seeded, login_as):
    trip = await _first_trip(seeded, TripStatus.SUBMITTED)
    approver = await login_as(await _email_of(seeded, trip.approver_id))
    owner = await login_as(await _email_of(seeded, trip.user_id))

    rejected = await client.post(
        f"/api/v1/trips/{trip.id}/reject", headers=approver, json={"reason": "예산 초과"}
    )
    assert rejected.status_code == 200
    assert rejected.json()["reject_reason"] == "예산 초과"

    reopened = await client.post(f"/api/v1/trips/{trip.id}/reopen", headers=owner)
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "DRAFT"

    resubmitted = await client.post(f"/api/v1/trips/{trip.id}/submit", headers=owner)
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "SUBMITTED"
    assert resubmitted.json()["reject_reason"] is None


async def test_complete_requires_the_trip_to_have_ended(client, seeded, login_as):
    trip = await _first_trip(seeded, TripStatus.APPROVED)
    trip.start_date = date.today() + timedelta(days=3)
    trip.end_date = date.today() + timedelta(days=5)
    await seeded.flush()
    headers = await login_as(await _email_of(seeded, trip.user_id))

    response = await client.post(f"/api/v1/trips/{trip.id}/complete", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRIP_NOT_ENDED"


async def test_complete_after_the_end_date(client, seeded, login_as):
    trip = await _first_trip(seeded, TripStatus.APPROVED)
    trip.start_date = date.today() - timedelta(days=10)
    trip.end_date = date.today() - timedelta(days=8)
    await seeded.flush()
    headers = await login_as(await _email_of(seeded, trip.user_id))

    response = await client.post(f"/api/v1/trips/{trip.id}/complete", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"


async def test_settled_transition_is_not_reachable_over_http(client, seeded, login_as):
    """COMPLETED → SETTLED는 정산서 승인이 트리거하는 시스템 전이다. 직접 부를 수 있는
    엔드포인트가 있어서는 안 된다."""
    trip = await _first_trip(seeded, TripStatus.COMPLETED)
    headers = await login_as(await _email_of(seeded, trip.user_id))

    response = await client.post(f"/api/v1/trips/{trip.id}/settle", headers=headers)

    assert response.status_code == 404


async def test_timeline_lists_transitions_with_actor_names(client, seeded, login_as):
    trip = await _first_trip(seeded, TripStatus.DRAFT)
    owner = await login_as(await _email_of(seeded, trip.user_id))
    await client.post(f"/api/v1/trips/{trip.id}/submit", headers=owner)

    response = await client.get(f"/api/v1/trips/{trip.id}/timeline", headers=owner)

    assert response.status_code == 200
    entries = response.json()
    assert entries[-1]["action"] == "SUBMITTED"
    assert entries[-1]["actor_name"]
    assert entries[-1]["to_status"] == "SUBMITTED"


async def test_notification_reaches_the_approver(client, seeded, login_as):
    trip = await _first_trip(seeded, TripStatus.DRAFT)
    owner = await login_as(await _email_of(seeded, trip.user_id))

    await client.post(f"/api/v1/trips/{trip.id}/submit", headers=owner)

    rows = (await seeded.execute(select(Notification))).scalars().all()
    assert any(n.link_url == f"/trips/{trip.id}" for n in rows)
