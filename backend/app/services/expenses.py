"""정산 서비스. 라우터는 이 모듈의 함수만 부르고 스키마를 그대로 응답한다.

`relationship()`을 붙이지 않는다 — 출장 제목·사용자 이름은 id를 모아 한 번에 조회한다.
목록에서 행마다 헬퍼를 부르면 N+1이 되고, 그걸 막는 쿼리 수 고정 테스트가 붙어 있다.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, EntityType, ExpenseReportStatus, UserRole
from app.errors import ConflictError, ForbiddenError, NotFoundError
from app.models import CardTransaction, ExpenseItem, ExpenseReport, Trip, User
from app.schemas.common import Page
from app.schemas.expense import (
    ExpenseItemOut,
    ExpenseReportCreate,
    ExpenseReportDetail,
    ExpenseReportListItem,
    ExpenseReportUpdate,
)
from app.services.centers import assert_cost_center, assert_fund_center
from app.services.expense_rules import (
    assert_report_creatable,
    assert_report_editable,
    assert_report_owner,
    can_view_report,
    effective_center,
)
from app.services.history import record_transition
from app.services.numbering import next_report_no
from app.services.trip_rules import assert_trip_owner
from app.services.trips import load_user_names, load_visible_trip


@dataclass(frozen=True)
class ExpenseFilters:
    scope: str = "mine"
    status: list[ExpenseReportStatus] = field(default_factory=list)
    q: str | None = None
    page: int = 1
    size: int = 20


async def build_list_items(
    session: AsyncSession, reports: list[ExpenseReport]
) -> list[ExpenseReportListItem]:
    if not reports:
        return []
    trip_rows = (
        await session.execute(
            select(Trip.id, Trip.trip_no, Trip.title, Trip.start_date, Trip.end_date).where(
                Trip.id.in_({report.trip_id for report in reports})
            )
        )
    ).all()
    trips = {row[0]: row for row in trip_rows}
    names = await load_user_names(
        session,
        {report.user_id for report in reports}
        | {report.approver_id for report in reports if report.approver_id is not None},
    )
    items: list[ExpenseReportListItem] = []
    for report in reports:
        trip = trips[report.trip_id]
        items.append(
            ExpenseReportListItem(
                id=report.id,
                report_no=report.report_no,
                status=report.status,
                trip_id=report.trip_id,
                trip_no=trip[1],
                trip_title=trip[2],
                trip_start_date=trip[3],
                trip_end_date=trip[4],
                user_id=report.user_id,
                user_name=names.get(report.user_id, ""),
                approver_id=report.approver_id,
                approver_name=names.get(report.approver_id) if report.approver_id else None,
                fund_center_code=report.fund_center_code,
                cost_center_code=report.cost_center_code,
                total_amount_krw=report.total_amount_krw,
                submitted_at=report.submitted_at,
                approved_at=report.approved_at,
            )
        )
    return items


async def _load_items(session: AsyncSession, report: ExpenseReport) -> list[ExpenseItemOut]:
    rows = (
        (
            await session.execute(
                select(ExpenseItem)
                .where(ExpenseItem.report_id == report.id)
                .order_by(ExpenseItem.id)
            )
        )
        .scalars()
        .all()
    )
    transaction_ids = {row.card_transaction_id for row in rows if row.card_transaction_id}
    transactions: dict[int, tuple] = {}
    if transaction_ids:
        transaction_rows = (
            await session.execute(
                select(
                    CardTransaction.id, CardTransaction.merchant_name, CardTransaction.approved_at
                ).where(CardTransaction.id.in_(transaction_ids))
            )
        ).all()
        transactions = {row[0]: row for row in transaction_rows}
    return [
        ExpenseItemOut(
            id=row.id,
            card_transaction_id=row.card_transaction_id,
            expense_category_code=row.expense_category_code,
            amount_krw=row.amount_krw,
            memo=row.memo,
            is_excluded=row.is_excluded,
            fund_center_code=row.fund_center_code,
            cost_center_code=row.cost_center_code,
            effective_fund_center_code=effective_center(
                row.fund_center_code, report.fund_center_code
            ),
            effective_cost_center_code=effective_center(
                row.cost_center_code, report.cost_center_code
            ),
            merchant_name=(
                transactions[row.card_transaction_id][1]
                if row.card_transaction_id in transactions
                else None
            ),
            approved_at=(
                transactions[row.card_transaction_id][2]
                if row.card_transaction_id in transactions
                else None
            ),
        )
        for row in rows
    ]


async def build_detail(session: AsyncSession, report: ExpenseReport) -> ExpenseReportDetail:
    [item] = await build_list_items(session, [report])
    return ExpenseReportDetail(
        **item.model_dump(),
        reject_reason=report.reject_reason,
        created_at=report.created_at,
        updated_at=report.updated_at,
        items=await _load_items(session, report),
    )


async def load_visible_report(
    session: AsyncSession, report_id: int, user: User
) -> ExpenseReport:
    """볼 수 없는 정산서는 없는 것으로 취급한다 (spec 7: 타인 리소스 접근도 404)."""
    report = await session.get(ExpenseReport, report_id)
    if report is None or not can_view_report(
        user_id=user.id,
        role=user.role,
        owner_id=report.user_id,
        approver_id=report.approver_id,
    ):
        raise NotFoundError("EXPENSE_NOT_FOUND", "정산서를 찾을 수 없습니다")
    return report


def _scope_conditions(user: User, scope: str) -> list[ColumnElement[bool]]:
    if scope == "mine":
        return [ExpenseReport.user_id == user.id]
    if scope == "approvals":
        return [ExpenseReport.approver_id == user.id]
    if user.role is not UserRole.ADMIN:
        raise ForbiddenError("FORBIDDEN_SCOPE", "전체 정산서를 조회할 권한이 없습니다")
    return []


async def list_reports(
    session: AsyncSession, *, user: User, filters: ExpenseFilters
) -> Page[ExpenseReportListItem]:
    conditions = _scope_conditions(user, filters.scope)
    if filters.status:
        conditions.append(ExpenseReport.status.in_(filters.status))
    if filters.q:
        # 사용자 입력의 % 와 _ 는 이스케이프하지 않는다 — 출장 목록과 같은 판단이다.
        like = f"%{filters.q}%"
        conditions.append(
            or_(
                ExpenseReport.report_no.ilike(like),
                Trip.title.ilike(like),
                Trip.trip_no.ilike(like),
            )
        )

    total = (
        await session.execute(
            select(func.count())
            .select_from(ExpenseReport)
            .join(Trip, Trip.id == ExpenseReport.trip_id)
            .where(*conditions)
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(ExpenseReport)
                .join(Trip, Trip.id == ExpenseReport.trip_id)
                .where(*conditions)
                .order_by(ExpenseReport.id.desc())
                .offset((filters.page - 1) * filters.size)
                .limit(filters.size)
            )
        )
        .scalars()
        .all()
    )
    return Page[ExpenseReportListItem](
        items=await build_list_items(session, list(rows)),
        total=total,
        page=filters.page,
        size=filters.size,
    )


async def get_report(
    session: AsyncSession, *, user: User, report_id: int
) -> ExpenseReportDetail:
    return await build_detail(session, await load_visible_report(session, report_id, user))


async def create_report(
    session: AsyncSession, *, user: User, payload: ExpenseReportCreate
) -> ExpenseReportDetail:
    trip = await load_visible_trip(session, payload.trip_id, user)
    assert_trip_owner(user_id=user.id, owner_id=trip.user_id)
    assert_report_creatable(trip.status)

    existing = (
        await session.execute(select(ExpenseReport.id).where(ExpenseReport.trip_id == trip.id))
    ).scalar_one_or_none()
    if existing is not None:
        # trip_id에 unique 제약이 있으므로 이 검사가 없으면 flush에서 IntegrityError가
        # 나고 catch-all 핸들러에 걸려 500이 된다. Agent는 5xx를 재시도한다.
        raise ConflictError("EXPENSE_ALREADY_EXISTS", "이 출장의 정산서가 이미 있습니다")

    report = ExpenseReport(
        report_no=await next_report_no(session, datetime.now(timezone.utc).date()),
        trip_id=trip.id,
        user_id=trip.user_id,
        status=ExpenseReportStatus.DRAFT,
        # cost_center_code는 출장에서 승계된다 (spec 5.5). fund_center_code는 출장에
        # 없으므로 비워 두고, 제출 전에 사용자가 고른다.
        cost_center_code=trip.cost_center_code,
        fund_center_code=None,
        approver_id=trip.approver_id,
        total_amount_krw=Decimal("0"),
    )
    session.add(report)
    await session.flush()
    await record_transition(
        session,
        entity_type=EntityType.EXPENSE_REPORT,
        entity_id=report.id,
        actor_id=user.id,
        action=ActivityAction.CREATED,
        to_status=ExpenseReportStatus.DRAFT.value,
        memo=f"{trip.trip_no} 정산서 작성",
    )
    await session.commit()
    return await build_detail(session, report)


async def update_report(
    session: AsyncSession, *, user: User, report_id: int, payload: ExpenseReportUpdate
) -> ExpenseReportDetail:
    report = await load_visible_report(session, report_id, user)
    assert_report_owner(user_id=user.id, owner_id=report.user_id)
    assert_report_editable(report.status)

    changes = payload.model_dump(exclude_unset=True)
    if changes.get("fund_center_code") is not None:
        await assert_fund_center(session, changes["fund_center_code"])
    if changes.get("cost_center_code") is not None:
        await assert_cost_center(session, changes["cost_center_code"])

    for name, value in changes.items():
        setattr(report, name, value)
    await session.flush()
    await record_transition(
        session,
        entity_type=EntityType.EXPENSE_REPORT,
        entity_id=report.id,
        actor_id=user.id,
        action=ActivityAction.UPDATED,
        from_status=report.status.value,
        to_status=report.status.value,
        memo="정산서 헤더 수정",
    )
    await session.commit()
    return await build_detail(session, report)
