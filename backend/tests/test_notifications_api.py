from sqlalchemy import select

from app.enums import TripStatus
from app.models import Trip, User


async def _submit_one_trip(client, session, login_as) -> tuple[dict, str]:
    """시드의 DRAFT 출장을 상신해 결재자에게 알림을 만든다. (결재자 헤더, 출장 링크) 반환."""
    trip = (
        (
            await session.execute(
                select(Trip).where(Trip.status == TripStatus.DRAFT).order_by(Trip.id)
            )
        )
        .scalars()
        .first()
    )
    owner = await session.get(User, trip.user_id)
    owner_headers = await login_as(owner.email)
    await client.post(f"/api/v1/trips/{trip.id}/submit", headers=owner_headers)
    await session.refresh(trip)
    approver = await session.get(User, trip.approver_id)
    return await login_as(approver.email), f"/trips/{trip.id}"


async def test_notifications_require_authentication(client, seeded):
    assert (await client.get("/api/v1/notifications")).status_code == 401


async def test_list_returns_my_notifications_with_unread_count(client, seeded, login_as):
    approver_headers, link = await _submit_one_trip(client, seeded, login_as)

    response = await client.get("/api/v1/notifications", headers=approver_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["unread"] >= 1
    assert body["items"][0]["link_url"] == link
    assert body["items"][0]["is_read"] is False


async def test_list_can_filter_unread_only(client, seeded, login_as):
    approver_headers, _ = await _submit_one_trip(client, seeded, login_as)
    listed = await client.get("/api/v1/notifications", headers=approver_headers)
    notification_id = listed.json()["items"][0]["id"]
    await client.post(f"/api/v1/notifications/{notification_id}/read", headers=approver_headers)

    response = await client.get(
        "/api/v1/notifications", headers=approver_headers, params={"unread_only": "true"}
    )

    assert notification_id not in [item["id"] for item in response.json()["items"]]
    assert response.json()["unread"] == 0


async def test_mark_read_returns_the_updated_notification(client, seeded, login_as):
    approver_headers, _ = await _submit_one_trip(client, seeded, login_as)
    listed = await client.get("/api/v1/notifications", headers=approver_headers)
    notification_id = listed.json()["items"][0]["id"]

    response = await client.post(
        f"/api/v1/notifications/{notification_id}/read", headers=approver_headers
    )

    assert response.status_code == 200
    assert response.json()["is_read"] is True


async def test_cannot_read_someone_elses_notification(client, seeded, login_as):
    approver_headers, _ = await _submit_one_trip(client, seeded, login_as)
    listed = await client.get("/api/v1/notifications", headers=approver_headers)
    notification_id = listed.json()["items"][0]["id"]
    stranger = await login_as("user2@skon.example")

    response = await client.post(f"/api/v1/notifications/{notification_id}/read", headers=stranger)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"


async def test_i_do_not_see_other_peoples_notifications(client, seeded, login_as):
    await _submit_one_trip(client, seeded, login_as)
    stranger = await login_as("user2@skon.example")

    response = await client.get("/api/v1/notifications", headers=stranger)

    assert response.json()["total"] == 0
    assert response.json()["unread"] == 0
