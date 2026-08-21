"""출장 서비스. 라우터는 이 모듈의 함수만 부르고 스키마를 그대로 응답한다.

이름 컬럼(user_name·approver_name)은 relationship 없이 id를 모아 한 번에 조회한다.
`relationship(lazy="selectin")`을 습관적으로 붙이지 말 것 — 이 프로젝트는 의도치 않은
eager loading을 이미 세 번 되돌린 이력이 있다. 목록에서 행마다 헬퍼를 부르면 N+1이 된다.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, EntityType, NotificationType, TripStatus, UserRole
from app.errors import ForbiddenError, NotFoundError
from app.models import ActivityLog, CostCenter, Trip, User
from app.schemas.common import Page
from app.schemas.trip import (
    RejectRequest,
    TimelineEntry,
    TripCreate,
    TripDetail,
    TripListItem,
    TripUpdate,
)
from app.services.codes import validate_codes
from app.services.history import NotifySpec, record_transition
from app.services.numbering import next_trip_no
from app.services.trip_rules import (
    assert_completable,
    assert_date_range,
    assert_deletable,
    assert_editable,
    assert_has_approver,
    assert_reject_reason,
    assert_system_transition,
    assert_transition_allowed,
    assert_trip_owner,
    can_view_trip,
)

# assert_trip_transition·assert_trip_approver를 직접 import하지 않는다. 전이 검사는 전부
# assert_transition_allowed 하나를 지나야 하며, 두 검사를 따로 부를 수 있게 열어두면
# 언젠가 한쪽만 부르고 그 실패는 조용하다 — 출장을 볼 수 있는 결재자가 신청자 전용
# 전이를 통과하게 된다.


@dataclass(frozen=True)
class TripFilters:
    scope: str = "mine"
    status: list[TripStatus] = field(default_factory=list)
    destination_type_code: str | None = None
    country_code: str | None = None
    q: str | None = None
    start_date_from: date | None = None
    start_date_to: date | None = None
    page: int = 1
    size: int = 20


async def load_user_names(session: AsyncSession, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = await session.execute(select(User.id, User.name).where(User.id.in_(user_ids)))
    return {user_id: name for user_id, name in rows}


async def build_list_items(session: AsyncSession, trips: list[Trip]) -> list[TripListItem]:
    ids = {trip.user_id for trip in trips} | {
        trip.approver_id for trip in trips if trip.approver_id is not None
    }
    names = await load_user_names(session, ids)
    return [
        TripListItem(
            id=trip.id,
            trip_no=trip.trip_no,
            title=trip.title,
            city=trip.city,
            country_code=trip.country_code,
            destination_type_code=trip.destination_type_code,
            purpose_code=trip.purpose_code,
            start_date=trip.start_date,
            end_date=trip.end_date,
            status=trip.status,
            user_id=trip.user_id,
            user_name=names.get(trip.user_id, ""),
            approver_id=trip.approver_id,
            approver_name=names.get(trip.approver_id) if trip.approver_id else None,
        )
        for trip in trips
    ]


async def build_detail(session: AsyncSession, trip: Trip) -> TripDetail:
    [item] = await build_list_items(session, [trip])
    # 코스트센터가 비어 있으면 조회 자체를 건너뛴다. None으로 where를 걸면 항상 0건이라
    # 결과는 같지만 쓸모없는 왕복이 한 번 생긴다.
    cost_center_name = (
        (
            await session.execute(
                select(CostCenter.name).where(CostCenter.code == trip.cost_center_code)
            )
        ).scalar_one_or_none()
        if trip.cost_center_code
        else None
    )
    return TripDetail(
        **item.model_dump(),
        purpose_detail=trip.purpose_detail,
        cost_center_code=trip.cost_center_code,
        cost_center_name=cost_center_name,
        submitted_at=trip.submitted_at,
        approved_at=trip.approved_at,
        reject_reason=trip.reject_reason,
        created_at=trip.created_at,
        updated_at=trip.updated_at,
    )


async def load_visible_trip(session: AsyncSession, trip_id: int, user: User) -> Trip:
    """볼 수 없는 출장은 없는 것으로 취급한다 (spec 7: 타인 리소스 접근도 404)."""
    trip = await session.get(Trip, trip_id)
    if trip is None or not can_view_trip(
        user_id=user.id, role=user.role, owner_id=trip.user_id, approver_id=trip.approver_id
    ):
        raise NotFoundError("TRIP_NOT_FOUND", "출장을 찾을 수 없습니다")
    return trip


def _scope_conditions(user: User, scope: str) -> list[ColumnElement[bool]]:
    if scope == "mine":
        return [Trip.user_id == user.id]
    if scope == "approvals":
        # EMPLOYEE가 불러도 막지 않는다 — 결재자로 배정된 적이 없으면 그냥 0건이다.
        # 역할로 막으면 "팀장으로 승격됐는데 결재함이 안 열린다" 같은 상태 의존이 생긴다.
        return [Trip.approver_id == user.id]
    if user.role is not UserRole.ADMIN:
        raise ForbiddenError("FORBIDDEN_SCOPE", "전체 출장을 조회할 권한이 없습니다")
    return []


async def list_trips(
    session: AsyncSession, *, user: User, filters: TripFilters
) -> Page[TripListItem]:
    conditions = _scope_conditions(user, filters.scope)
    if filters.status:
        conditions.append(Trip.status.in_(filters.status))
    if filters.destination_type_code:
        conditions.append(Trip.destination_type_code == filters.destination_type_code)
    if filters.country_code:
        conditions.append(Trip.country_code == filters.country_code)
    if filters.start_date_from:
        conditions.append(Trip.start_date >= filters.start_date_from)
    if filters.start_date_to:
        conditions.append(Trip.start_date <= filters.start_date_to)
    if filters.q:
        # 사용자 입력의 % 와 _ 는 이스케이프하지 않는다. 검색 범위가 넓어질 뿐이고
        # 데모 규모에서 실질적 문제가 없다.
        like = f"%{filters.q}%"
        conditions.append(
            or_(Trip.title.ilike(like), Trip.city.ilike(like), Trip.trip_no.ilike(like))
        )

    total = (
        await session.execute(select(func.count()).select_from(Trip).where(*conditions))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(Trip)
                .where(*conditions)
                .order_by(Trip.start_date.desc(), Trip.id.desc())
                .offset((filters.page - 1) * filters.size)
                .limit(filters.size)
            )
        )
        .scalars()
        .all()
    )
    return Page[TripListItem](
        items=await build_list_items(session, list(rows)),
        total=total,
        page=filters.page,
        size=filters.size,
    )


async def get_trip(session: AsyncSession, *, user: User, trip_id: int) -> TripDetail:
    return await build_detail(session, await load_visible_trip(session, trip_id, user))


#: 코드값 검증이 필요한 필드. (group_code, 필드명) 짝을 여기 한 곳에서만 관리한다.
#: 손으로 세 쌍을 나열하지 않기 때문에 그룹과 field를 잘못 짝지을 수 없다.
_CODE_FIELDS: tuple[tuple[str, str], ...] = (
    ("TRIP_PURPOSE", "purpose_code"),
    ("DESTINATION_TYPE", "destination_type_code"),
    ("COUNTRY", "country_code"),
)

#: 생성·수정 양쪽에서 검증해야 하는 필드. 수정은 부분 갱신이므로 병합 결과를 넘긴다.
_VALIDATED_FIELDS: tuple[str, ...] = (
    *(field_name for _, field_name in _CODE_FIELDS),
    "start_date",
    "end_date",
)


async def _validate_writable_fields(session: AsyncSession, values: dict) -> None:
    await validate_codes(
        session, [(group, field_name, values[field_name]) for group, field_name in _CODE_FIELDS]
    )
    assert_date_range(start_date=values["start_date"], end_date=values["end_date"])


async def create_trip(session: AsyncSession, *, user: User, payload: TripCreate) -> TripDetail:
    values = payload.model_dump()
    await _validate_writable_fields(session, values)

    trip = Trip(
        **values,
        trip_no=await next_trip_no(session, date.today()),
        user_id=user.id,
        status=TripStatus.DRAFT,
    )
    session.add(trip)
    await session.flush()
    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.CREATED,
        to_status=TripStatus.DRAFT.value,
        memo="출장 신청서 작성",
    )
    await session.commit()
    return await build_detail(session, trip)


async def update_trip(
    session: AsyncSession, *, user: User, trip_id: int, payload: TripUpdate
) -> TripDetail:
    trip = await load_visible_trip(session, trip_id, user)
    assert_trip_owner(user_id=user.id, owner_id=trip.user_id)
    assert_editable(trip.status)

    changes = payload.model_dump(exclude_unset=True)
    # 보낸 필드만이 아니라 **병합 결과**를 검증한다. end_date만 바꿔도 start_date와의
    # 관계가 깨질 수 있고, destination_type만 바꿔도 country와 어긋날 수 있다.
    merged = {name: changes.get(name, getattr(trip, name)) for name in _VALIDATED_FIELDS}
    await _validate_writable_fields(session, merged)

    for name, value in changes.items():
        setattr(trip, name, value)
    await session.flush()
    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.UPDATED,
        from_status=trip.status.value,
        to_status=trip.status.value,
        memo="출장 정보 수정",
    )
    await session.commit()
    return await build_detail(session, trip)


async def delete_trip(session: AsyncSession, *, user: User, trip_id: int) -> None:
    trip = await load_visible_trip(session, trip_id, user)
    assert_trip_owner(user_id=user.id, owner_id=trip.user_id)
    assert_deletable(trip.status)
    # activity_log.entity_id에는 FK가 없으므로 함께 지울 것이 없다. 삭제된 출장의
    # 이력이 남지만, 임시저장만 삭제 가능하므로 남는 이력은 CREATED/UPDATED뿐이다.
    await session.delete(trip)
    await session.commit()


def _link(trip: Trip) -> str:
    return f"/trips/{trip.id}"


def _assert_transition(trip: Trip, user: User, target: TripStatus) -> None:
    """전이 검사는 이 한 줄만 부른다.

    적법성과 수행 주체를 따로 부르던 때는 한쪽을 빠뜨려도 조용했고, 그 실패는
    fail-open이었다 — 출장을 볼 수 있는 결재자가 신청자 전용 전이를 통과했다.
    owner_id·approver_id 추출도 여기 한 곳에서만 하므로 잘못된 id를 넘길 자리가 없다.
    """
    assert_transition_allowed(
        trip.status,
        target,
        user_id=user.id,
        owner_id=trip.user_id,
        approver_id=trip.approver_id,
    )


async def submit_trip(session: AsyncSession, *, user: User, trip_id: int) -> TripDetail:
    trip = await load_visible_trip(session, trip_id, user)
    _assert_transition(trip, user, TripStatus.SUBMITTED)
    # 모델에 CheckConstraint가 없으므로 상신 시점에 한 번 더 본다. DB를 직접 고친
    # 데이터가 결재로 흘러가는 것을 막는 마지막 지점이다.
    assert_date_range(start_date=trip.start_date, end_date=trip.end_date)
    approver_id = assert_has_approver(user.manager_id)

    from_status = trip.status
    trip.status = TripStatus.SUBMITTED
    trip.approver_id = approver_id
    trip.submitted_at = datetime.now(timezone.utc)
    trip.approved_at = None
    trip.reject_reason = None
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.SUBMITTED,
        from_status=from_status.value,
        to_status=TripStatus.SUBMITTED.value,
        notify=NotifySpec(
            user_id=approver_id,
            type=NotificationType.TRIP_SUBMITTED,
            title="출장 결재 요청",
            body=f"{user.name}님이 '{trip.title}' 출장을 상신했습니다.",
            link_url=_link(trip),
        ),
    )
    await session.commit()
    return await build_detail(session, trip)


async def approve_trip(session: AsyncSession, *, user: User, trip_id: int) -> TripDetail:
    trip = await load_visible_trip(session, trip_id, user)
    _assert_transition(trip, user, TripStatus.APPROVED)

    from_status = trip.status
    trip.status = TripStatus.APPROVED
    trip.approved_at = datetime.now(timezone.utc)
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.APPROVED,
        from_status=from_status.value,
        to_status=TripStatus.APPROVED.value,
        notify=NotifySpec(
            user_id=trip.user_id,
            type=NotificationType.TRIP_APPROVED,
            title="출장이 승인되었습니다",
            body=f"'{trip.title}' 출장이 {user.name}님에게 승인되었습니다.",
            link_url=_link(trip),
        ),
    )
    await session.commit()
    return await build_detail(session, trip)


async def reject_trip(
    session: AsyncSession, *, user: User, trip_id: int, payload: RejectRequest
) -> TripDetail:
    trip = await load_visible_trip(session, trip_id, user)
    _assert_transition(trip, user, TripStatus.REJECTED)
    reason = assert_reject_reason(payload.reason)

    from_status = trip.status
    trip.status = TripStatus.REJECTED
    trip.reject_reason = reason
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.REJECTED,
        from_status=from_status.value,
        to_status=TripStatus.REJECTED.value,
        memo=reason,
        notify=NotifySpec(
            user_id=trip.user_id,
            type=NotificationType.TRIP_REJECTED,
            title="출장이 반려되었습니다",
            body=f"'{trip.title}' 출장이 반려되었습니다. 사유: {reason}",
            link_url=_link(trip),
        ),
    )
    await session.commit()
    return await build_detail(session, trip)


async def reopen_trip(session: AsyncSession, *, user: User, trip_id: int) -> TripDetail:
    """반려된 출장을 임시저장으로 되돌려 재상신할 수 있게 한다 (spec 5.4의 REJECTED → DRAFT).

    spec 7의 엔드포인트 목록에는 없지만 spec 5.4의 상태도가 요구하는 전이다. 이것이
    없으면 반려된 출장은 영원히 반려 상태로 남는다.
    """
    trip = await load_visible_trip(session, trip_id, user)
    _assert_transition(trip, user, TripStatus.DRAFT)

    from_status = trip.status
    trip.status = TripStatus.DRAFT
    trip.approver_id = None
    trip.submitted_at = None
    trip.approved_at = None
    # reject_reason은 남긴다 — 무엇을 고쳐야 하는지 화면에서 계속 보여야 한다.
    # 다음 상신에서 submit_trip이 지운다.
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.UPDATED,
        from_status=from_status.value,
        to_status=TripStatus.DRAFT.value,
        memo="재작성을 위해 임시저장으로 되돌림",
    )
    await session.commit()
    return await build_detail(session, trip)


async def complete_trip(session: AsyncSession, *, user: User, trip_id: int) -> TripDetail:
    trip = await load_visible_trip(session, trip_id, user)
    _assert_transition(trip, user, TripStatus.COMPLETED)
    assert_completable(trip.end_date, today=date.today())

    from_status = trip.status
    trip.status = TripStatus.COMPLETED
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.COMPLETED,
        from_status=from_status.value,
        to_status=TripStatus.COMPLETED.value,
        memo="출장 완료 처리",
    )
    await session.commit()
    return await build_detail(session, trip)


async def list_timeline(session: AsyncSession, *, user: User, trip_id: int) -> list[TimelineEntry]:
    trip = await load_visible_trip(session, trip_id, user)
    rows = (
        (
            await session.execute(
                select(ActivityLog)
                .where(
                    ActivityLog.entity_type == EntityType.TRIP,
                    ActivityLog.entity_id == trip.id,
                )
                .order_by(ActivityLog.created_at, ActivityLog.id)
            )
        )
        .scalars()
        .all()
    )
    names = await load_user_names(session, {row.actor_id for row in rows})
    return [
        TimelineEntry(
            id=row.id,
            action=row.action,
            from_status=row.from_status,
            to_status=row.to_status,
            memo=row.memo,
            actor_id=row.actor_id,
            actor_name=names.get(row.actor_id, ""),
            created_at=row.created_at,
        )
        for row in rows
    ]


async def settle_trip_for_report(
    session: AsyncSession, *, trip: Trip, actor_id: int, report_no: str
) -> None:
    """정산서 승인이 트리거하는 COMPLETED → SETTLED (spec 5.4).

    commit하지 않는다 — 정산서 승인과 **같은 트랜잭션**에서 끝나야 한다. 따로 커밋하면
    정산서는 승인됐는데 출장은 COMPLETED로 남는 상태가 만들어질 수 있다.

    사용자 경로(`assert_transition_allowed`)로는 이 전이를 통과할 수 없고, 반대로 이
    함수는 사용자 주체 전이를 거부한다.
    """
    assert_system_transition(trip.status, TripStatus.SETTLED)

    from_status = trip.status
    trip.status = TripStatus.SETTLED
    await session.flush()
    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=actor_id,
        action=ActivityAction.SETTLED,
        from_status=from_status.value,
        to_status=TripStatus.SETTLED.value,
        # 알림은 정산서 쪽에서 EXPENSE_APPROVED 하나만 보낸다. 한 번의 승인으로 알림
        # 두 개를 받을 이유가 없고, NotificationType에 TRIP_SETTLED도 없다.
        memo=f"정산서 {report_no} 승인으로 정산 완료",
    )
