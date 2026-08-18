"""법인카드·카드거래 조회.

카드 소유자 필터는 **서비스가** 건다. 라우터가 card_id를 그대로 where에 넣으면 남의
카드 id를 넣었을 때 남의 거래가 새어나간다 — 이 프로젝트는 타인 리소스를 404/0건으로
다룬다.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CardTransaction, CorporateCard, User
from app.schemas.card import CardOut, CardTransactionOut
from app.schemas.common import Page
from app.services.matching import KST


def _start_of(day: date, *, plus_one: bool = False) -> datetime:
    """날짜 필터는 KST 자정 경계로 자른다. approved_at이 timestamptz이므로 date를 그대로
    비교하면 UTC 경계가 되어 화면에 보이는 날짜와 어긋난다."""
    target = day + timedelta(days=1) if plus_one else day
    return datetime.combine(target, time.min, tzinfo=KST)


@dataclass(frozen=True)
class CardTxnFilters:
    card_id: int | None = None
    approved_from: date | None = None
    approved_to: date | None = None
    merchant_category_code: str | None = None
    q: str | None = None
    include_cancelled: bool = False
    page: int = 1
    size: int = 20


async def load_my_card_ids(session: AsyncSession, user: User) -> list[int]:
    rows = await session.execute(
        select(CorporateCard.id).where(CorporateCard.user_id == user.id)
    )
    return list(rows.scalars().all())


async def list_my_cards(session: AsyncSession, *, user: User) -> list[CardOut]:
    rows = (
        (
            await session.execute(
                select(CorporateCard)
                .where(CorporateCard.user_id == user.id)
                .order_by(CorporateCard.id)
            )
        )
        .scalars()
        .all()
    )
    return [CardOut.model_validate(row) for row in rows]


async def list_card_transactions(
    session: AsyncSession, *, user: User, filters: CardTxnFilters
) -> Page[CardTransactionOut]:
    card_ids = await load_my_card_ids(session, user)
    if filters.card_id is not None:
        # 교집합을 취한다. 남의 card_id면 빈 목록이 되고 존재 여부도 알려주지 않는다.
        card_ids = [card_id for card_id in card_ids if card_id == filters.card_id]
    if not card_ids:
        return Page[CardTransactionOut](items=[], total=0, page=filters.page, size=filters.size)

    conditions: list[ColumnElement[bool]] = [CardTransaction.card_id.in_(card_ids)]
    if not filters.include_cancelled:
        conditions.append(CardTransaction.is_cancelled.is_(False))
    if filters.approved_from:
        conditions.append(CardTransaction.approved_at >= _start_of(filters.approved_from))
    if filters.approved_to:
        conditions.append(
            CardTransaction.approved_at < _start_of(filters.approved_to, plus_one=True)
        )
    if filters.merchant_category_code:
        conditions.append(
            CardTransaction.merchant_category_code == filters.merchant_category_code
        )
    if filters.q:
        conditions.append(CardTransaction.merchant_name.ilike(f"%{filters.q}%"))

    total = (
        await session.execute(
            select(func.count()).select_from(CardTransaction).where(*conditions)
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(CardTransaction)
                .where(*conditions)
                .order_by(CardTransaction.approved_at.desc(), CardTransaction.id.desc())
                .offset((filters.page - 1) * filters.size)
                .limit(filters.size)
            )
        )
        .scalars()
        .all()
    )
    return Page[CardTransactionOut](
        items=[CardTransactionOut.model_validate(row) for row in rows],
        total=total,
        page=filters.page,
        size=filters.size,
    )
