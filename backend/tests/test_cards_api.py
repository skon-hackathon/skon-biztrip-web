"""카드 조회 API. 남의 카드·거래는 보이지 않아야 한다."""

from datetime import datetime, timezone
from decimal import Decimal

from app.enums import TripStatus
from app.services.cards import CardTxnFilters, list_card_transactions
from app.services.matching import suggest_expense_category
from tests.factories import (
    make_card,
    make_card_transaction,
    make_expense_item,
    make_expense_report,
    make_trip,
    make_user,
)


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


async def test_unsettled_hides_transactions_already_in_a_report(db_session):
    """정산 화면의 카드내역 피커가 쓰는 필터. 담긴 거래가 계속 보이면 사용자가 다시
    담으려다 409를 맞는다."""
    user = await make_user(db_session, name="미정산")
    card = await make_card(db_session, user=user)
    kept = await make_card_transaction(
        db_session, card=card, approved_at=datetime(2026, 5, 11, 3, tzinfo=timezone.utc)
    )
    taken = await make_card_transaction(
        db_session, card=card, approved_at=datetime(2026, 5, 12, 3, tzinfo=timezone.utc)
    )
    trip = await make_trip(db_session, user=user, status=TripStatus.COMPLETED)
    report = await make_expense_report(db_session, trip=trip)
    await make_expense_item(db_session, report=report, card_transaction=taken)
    await db_session.flush()

    everything = await list_card_transactions(db_session, user=user, filters=CardTxnFilters())
    unsettled = await list_card_transactions(
        db_session, user=user, filters=CardTxnFilters(unsettled=True)
    )

    assert {row.id for row in everything.items} == {kept.id, taken.id}
    assert [row.id for row in unsettled.items] == [kept.id]
    assert unsettled.total == 1


async def test_unsettled_does_not_collapse_when_items_have_no_transaction(db_session):
    """NOT IN 서브쿼리에 NULL이 섞이면 결과 전체가 0건이 된다. 카드 없이 손으로 적은
    정산 항목이 하나라도 있으면 그 상황이 되므로, 그 항목을 만들어 두고 확인한다."""
    user = await make_user(db_session, name="현금항목")
    card = await make_card(db_session, user=user)
    cash_free = await make_card_transaction(
        db_session, card=card, approved_at=datetime(2026, 5, 11, 3, tzinfo=timezone.utc)
    )
    trip = await make_trip(db_session, user=user, status=TripStatus.COMPLETED)
    report = await make_expense_report(db_session, trip=trip)
    await make_expense_item(db_session, report=report, card_transaction=None)
    await db_session.flush()

    unsettled = await list_card_transactions(
        db_session, user=user, filters=CardTxnFilters(unsettled=True)
    )

    assert [row.id for row in unsettled.items] == [cash_free.id]


async def test_unsettled_does_not_leak_other_peoples_transactions(db_session):
    user = await make_user(db_session, name="본인")
    other = await make_user(db_session, name="남의사람")
    await make_card_transaction(
        db_session,
        card=await make_card(db_session, user=other),
        approved_at=datetime(2026, 5, 11, 3, tzinfo=timezone.utc),
    )
    await db_session.flush()

    result = await list_card_transactions(
        db_session, user=user, filters=CardTxnFilters(unsettled=True)
    )

    assert result.total == 0


async def test_transactions_carry_the_suggested_expense_category(db_session):
    """업종→비목 매핑은 자동매칭과 같은 함수를 쓴다. 화면이 자기 매핑을 갖게 되면
    자동매칭이 추천하는 비목과 피커가 추천하는 비목이 갈라진다."""
    user = await make_user(db_session, name="비목추천")
    card = await make_card(db_session, user=user)
    await make_card_transaction(
        db_session,
        card=card,
        approved_at=datetime(2026, 5, 11, 3, tzinfo=timezone.utc),
        merchant_category_code="LODGING",
    )
    await db_session.flush()

    result = await list_card_transactions(db_session, user=user, filters=CardTxnFilters())

    assert result.items[0].suggested_expense_category_code == suggest_expense_category("LODGING")


async def test_cards_require_authentication(client):
    response = await client.get("/api/v1/cards")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_CREDENTIALS"
