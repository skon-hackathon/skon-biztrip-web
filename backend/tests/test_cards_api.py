"""카드 조회 API. 남의 카드·거래는 보이지 않아야 한다."""

from datetime import datetime, timezone
from decimal import Decimal

from app.services.cards import CardTxnFilters, list_card_transactions
from tests.factories import make_card, make_card_transaction, make_user


async def test_lists_only_my_cards(client, login_as, seeded):
    headers = await login_as("user1@skon.example")
    response = await client.get("/api/v1/cards", headers=headers)
    assert response.status_code == 200
    cards = response.json()
    assert len(cards) >= 1
    assert all("card_no_masked" in card for card in cards)


async def test_card_transactions_are_scoped_to_my_cards(client, db_session, login_as, seeded):
    """다른 사용자의 카드 id를 직접 넘겨도 남의 거래가 새지 않는다."""
    other = await make_user(db_session, name="남의사람")
    other_card = await make_card(db_session, user=other)
    await make_card_transaction(
        db_session, card=other_card, approved_at=datetime(2026, 5, 11, 3, tzinfo=timezone.utc)
    )
    await db_session.flush()

    headers = await login_as("user1@skon.example")
    response = await client.get(
        f"/api/v1/card-transactions?card_id={other_card.id}", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_card_transactions_filter_by_date_range(client, login_as, seeded):
    headers = await login_as("user1@skon.example")
    response = await client.get(
        "/api/v1/card-transactions?approved_from=2026-01-01&approved_to=2026-12-31&size=5",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["size"] == 5
    assert len(body["items"]) <= 5


async def test_cancelled_transactions_are_hidden_by_default(db_session, seeded):
    user = await make_user(db_session, name="취소테스트")
    card = await make_card(db_session, user=user)
    await make_card_transaction(
        db_session,
        card=card,
        approved_at=datetime(2026, 5, 11, 3, tzinfo=timezone.utc),
        is_cancelled=True,
        amount=Decimal("77000"),
    )
    await db_session.flush()

    # 이 사용자로 로그인할 수 없으므로(비밀번호 해시가 'x') 서비스 함수를 직접 부른다.
    visible = await list_card_transactions(db_session, user=user, filters=CardTxnFilters())
    assert visible.total == 0

    with_cancelled = await list_card_transactions(
        db_session, user=user, filters=CardTxnFilters(include_cancelled=True)
    )
    assert with_cancelled.total == 1


async def test_a_user_without_cards_gets_an_empty_page(db_session):
    user = await make_user(db_session, name="카드없음")
    result = await list_card_transactions(db_session, user=user, filters=CardTxnFilters())
    assert result.total == 0
    assert result.items == []


async def test_cards_require_authentication(client):
    response = await client.get("/api/v1/cards")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_CREDENTIALS"
