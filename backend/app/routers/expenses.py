from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import CurrentUser, DbSession
from app.enums import ExpenseReportStatus
from app.schemas.common import Page
from app.schemas.expense import (
    ExpenseItemCreate,
    ExpenseItemUpdate,
    ExpenseReportCreate,
    ExpenseReportDetail,
    ExpenseReportListItem,
    ExpenseReportUpdate,
    MatchCandidateOut,
)
from app.schemas.trip import RejectRequest, TimelineEntry
from app.services import expenses as expense_service

router = APIRouter(prefix="/api/v1", tags=["expenses"])


@router.get("/expenses", response_model=Page[ExpenseReportListItem])
async def list_expenses(
    user: CurrentUser,
    session: DbSession,
    scope: Annotated[str, Query(pattern="^(mine|approvals|all)$")] = "mine",
    # 파라미터 이름을 status로 두면 fastapi.status 모듈과 충돌한다. 쿼리스트링은 그대로다.
    status_: Annotated[list[ExpenseReportStatus] | None, Query(alias="status")] = None,
    q: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ExpenseReportListItem]:
    return await expense_service.list_reports(
        session,
        user=user,
        filters=expense_service.ExpenseFilters(
            scope=scope, status=status_ or [], q=q, page=page, size=size
        ),
    )


@router.post(
    "/expenses", response_model=ExpenseReportDetail, status_code=status.HTTP_201_CREATED
)
async def create_expense(
    payload: ExpenseReportCreate, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.create_report(session, user=user, payload=payload)


@router.get("/expenses/{report_id}", response_model=ExpenseReportDetail)
async def get_expense(
    report_id: int, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.get_report(session, user=user, report_id=report_id)


@router.patch("/expenses/{report_id}", response_model=ExpenseReportDetail)
async def update_expense(
    report_id: int, payload: ExpenseReportUpdate, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.update_report(
        session, user=user, report_id=report_id, payload=payload
    )


@router.get("/expenses/{report_id}/match-candidates", response_model=list[MatchCandidateOut])
async def list_match_candidates(
    report_id: int, user: CurrentUser, session: DbSession
) -> list[MatchCandidateOut]:
    return await expense_service.list_match_candidates(session, user=user, report_id=report_id)


@router.get("/expenses/{report_id}/timeline", response_model=list[TimelineEntry])
async def get_expense_timeline(
    report_id: int, user: CurrentUser, session: DbSession
) -> list[TimelineEntry]:
    return await expense_service.list_report_timeline(session, user=user, report_id=report_id)


@router.post(
    "/expenses/{report_id}/items",
    response_model=ExpenseReportDetail,
    status_code=status.HTTP_201_CREATED,
)
async def add_expense_item(
    report_id: int, payload: ExpenseItemCreate, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.add_item(
        session, user=user, report_id=report_id, payload=payload
    )


@router.patch("/expense-items/{item_id}", response_model=ExpenseReportDetail)
async def update_expense_item(
    item_id: int, payload: ExpenseItemUpdate, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.update_item(
        session, user=user, item_id=item_id, payload=payload
    )


@router.delete("/expense-items/{item_id}", response_model=ExpenseReportDetail)
async def delete_expense_item(
    item_id: int, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    """204가 아니라 갱신된 정산서를 돌려준다 — 합계와 항목 목록이 함께 바뀌므로
    호출자가 곧바로 다시 GET 해야 하는 왕복을 없앤다."""
    return await expense_service.delete_item(session, user=user, item_id=item_id)


@router.post("/expenses/{report_id}/submit", response_model=ExpenseReportDetail)
async def submit_expense(
    report_id: int, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.submit_report(session, user=user, report_id=report_id)


@router.post("/expenses/{report_id}/approve", response_model=ExpenseReportDetail)
async def approve_expense(
    report_id: int, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.approve_report(session, user=user, report_id=report_id)


@router.post("/expenses/{report_id}/reject", response_model=ExpenseReportDetail)
async def reject_expense(
    report_id: int, payload: RejectRequest, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.reject_report(
        session, user=user, report_id=report_id, payload=payload
    )


@router.post("/expenses/{report_id}/reopen", response_model=ExpenseReportDetail)
async def reopen_expense(
    report_id: int, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.reopen_report(session, user=user, report_id=report_id)
