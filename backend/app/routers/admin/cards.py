from fastapi import APIRouter, status

from app.deps import AdminUser, DbSession
from app.schemas.admin import AdminCardCreate, AdminCardOut, AdminCardUpdate
from app.services.admin import cards as service

router = APIRouter(prefix="/api/v1/admin/cards", tags=["admin"])


@router.get("", response_model=list[AdminCardOut])
async def list_cards(user: AdminUser, session: DbSession) -> list[AdminCardOut]:
    return await service.list_cards(session)


@router.post("", response_model=AdminCardOut, status_code=status.HTTP_201_CREATED)
async def create_card(
    payload: AdminCardCreate, user: AdminUser, session: DbSession
) -> AdminCardOut:
    return await service.create_card(session, payload=payload)


@router.patch("/{card_id}", response_model=AdminCardOut)
async def update_card(
    card_id: int, payload: AdminCardUpdate, user: AdminUser, session: DbSession
) -> AdminCardOut:
    return await service.update_card(session, card_id=card_id, payload=payload)


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(card_id: int, user: AdminUser, session: DbSession) -> None:
    await service.delete_card(session, card_id=card_id)
