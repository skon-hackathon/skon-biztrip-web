from sqlalchemy import select

from app.enums import ActivityAction, EntityType, NotificationType, TripStatus
from app.models import ActivityLog, Notification
from app.services.history import NotifySpec, record_transition
from tests.factories import make_trip, make_user


async def test_records_activity_log(db_session):
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user)

    await record_transition(
        db_session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.CREATED,
        to_status=TripStatus.DRAFT.value,
        memo="출장 신청서 작성",
    )

    log = (await db_session.execute(select(ActivityLog))).scalar_one()
    assert log.entity_type is EntityType.TRIP
    assert log.entity_id == trip.id
    assert log.actor_id == user.id
    assert log.action is ActivityAction.CREATED
    assert log.from_status is None
    assert log.to_status == "DRAFT"
    assert log.memo == "출장 신청서 작성"


async def test_records_notification_for_another_user(db_session):
    manager = await make_user(db_session, name="김연구")
    employee = await make_user(db_session, manager=manager)
    trip = await make_trip(db_session, user=employee)

    await record_transition(
        db_session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=employee.id,
        action=ActivityAction.SUBMITTED,
        from_status="DRAFT",
        to_status="SUBMITTED",
        notify=NotifySpec(
            user_id=manager.id,
            type=NotificationType.TRIP_SUBMITTED,
            title="출장 결재 요청",
            body="박출장님이 출장을 상신했습니다.",
            link_url=f"/trips/{trip.id}",
        ),
    )

    notification = (await db_session.execute(select(Notification))).scalar_one()
    assert notification.user_id == manager.id
    assert notification.type is NotificationType.TRIP_SUBMITTED
    assert notification.is_read is False
    assert notification.link_url == f"/trips/{trip.id}"


async def test_does_not_notify_the_actor_themselves(db_session):
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user)

    await record_transition(
        db_session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.APPROVED,
        notify=NotifySpec(
            user_id=user.id,
            type=NotificationType.TRIP_APPROVED,
            title="승인됨",
            body="본인이 본인 것을 승인",
        ),
    )

    assert (await db_session.execute(select(Notification))).scalars().all() == []
    assert len((await db_session.execute(select(ActivityLog))).scalars().all()) == 1


async def test_activity_log_is_written_without_notification(db_session):
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user)

    await record_transition(
        db_session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.COMPLETED,
        from_status="APPROVED",
        to_status="COMPLETED",
    )

    assert (await db_session.execute(select(Notification))).scalars().all() == []
    assert (await db_session.execute(select(ActivityLog))).scalar_one().to_status == "COMPLETED"
