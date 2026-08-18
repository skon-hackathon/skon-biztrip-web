"""법인카드 마스터 CRUD.

일반 `/cards`는 **본인** 카드만 준다(소유자 필터를 서비스가 건다). 관리자는 전부 봐야 하므로
필터가 없는 별도 조회를 둔다 — 기존 서비스에 "관리자면 필터 생략" 분기를 넣지 않는다.
그 분기는 언젠가 잘못된 호출자에게도 열린다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError, ValidationError
from app.models import CorporateCard, User
from app.schemas.admin import AdminCardCreate, AdminCardOut, AdminCardUpdate
from app.services.admin.common import delete_entity


async def _to_out(session: AsyncSession, cards: list[CorporateCard]) -> list[AdminCardOut]:
    owner_ids = {card.user_id for card in cards}
    names: dict[int, str] = {}
    if owner_ids:
        rows = await session.execute(select(User.id, User.name).where(User.id.in_(owner_ids)))
        names = {row[0]: row[1] for row in rows}
    return [
        AdminCardOut(
            id=card.id,
            user_id=card.user_id,
            user_name=names.get(card.user_id, ""),
            card_no_masked=card.card_no_masked,
            brand=card.brand,
            is_active=card.is_active,
        )
        for card in cards
    ]


async def list_cards(session: AsyncSession) -> list[AdminCardOut]:
    cards = (
        (await session.execute(select(CorporateCard).order_by(CorporateCard.id))).scalars().all()
    )
    return await _to_out(session, list(cards))


async def _load(session: AsyncSession, card_id: int) -> CorporateCard:
    card = await session.get(CorporateCard, card_id)
    if card is None:
        raise NotFoundError("CARD_NOT_FOUND", f"존재하지 않는 카드입니다: {card_id}")
    return card


async def create_card(session: AsyncSession, *, payload: AdminCardCreate) -> AdminCardOut:
    if await session.get(User, payload.user_id) is None:
        raise ValidationError(
            "INVALID_USER", f"존재하지 않는 사용자입니다: {payload.user_id}", field="user_id"
        )
    card = CorporateCard(
        user_id=payload.user_id,
        card_no_masked=payload.card_no_masked,
        brand=payload.brand,
        is_active=payload.is_active,
    )
    session.add(card)
    await session.commit()
    await session.refresh(card)
    return (await _to_out(session, [card]))[0]


async def update_card(
    session: AsyncSession, *, card_id: int, payload: AdminCardUpdate
) -> AdminCardOut:
    card = await _load(session, card_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(card, field, value)
    await session.commit()
    await session.refresh(card)
    return (await _to_out(session, [card]))[0]


async def delete_card(session: AsyncSession, *, card_id: int) -> None:
    card = await _load(session, card_id)
    await delete_entity(
        session, card, message="이 카드의 거래내역이 있어 삭제할 수 없습니다. 비활성화하세요"
    )
