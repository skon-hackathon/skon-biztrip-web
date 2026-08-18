from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser, DbSession
from app.schemas.card import CardOut, CardTransactionOut
from app.schemas.common import Page
from app.services import cards as card_service

router = APIRouter(prefix="/api/v1", tags=["cards"])


@router.get("/cards", response_model=list[CardOut])
async def list_cards(user: CurrentUser, session: DbSession) -> list[CardOut]:
    return await card_service.list_my_cards(session, user=user)


@router.get("/card-transactions", response_model=Page[CardTransactionOut])
async def list_card_transactions(
    user: CurrentUser,
    session: DbSession,
    card_id: int | None = None,
    approved_from: date | None = None,
    approved_to: date | None = None,
    merchant_category_code: str | None = None,
    q: str | None = None,
    include_cancelled: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[CardTransactionOut]:
    return await card_service.list_card_transactions(
        session,
        user=user,
        filters=card_service.CardTxnFilters(
            card_id=card_id,
            approved_from=approved_from,
            approved_to=approved_to,
            merchant_category_code=merchant_category_code,
            q=q,
            include_cancelled=include_cancelled,
            page=page,
            size=size,
        ),
    )
