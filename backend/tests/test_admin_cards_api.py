"""법인카드 Admin CRUD. card_transaction.card_id가 실제 FK라 삭제 변환이 여기서 검증된다."""

from datetime import datetime, timezone

from tests.factories import make_card, make_card_transaction, make_user


async def test_employee_cannot_list_admin_cards(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    assert (await client.get("/api/v1/admin/cards", headers=headers)).status_code == 403


async def test_admin_sees_all_cards_with_owner_names(client, seeded, login_as):
    """일반 /cards는 **내** 카드만 준다. 관리자는 전부 봐야 한다."""
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/admin/cards", headers=headers)

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 14
    assert all(row["user_name"] for row in rows)


async def test_admin_creates_a_card(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=1", headers=headers)).json()
    owner_id = users["items"][0]["id"]

    response = await client.post(
        "/api/v1/admin/cards",
        headers=headers,
        json={"user_id": owner_id, "card_no_masked": "1234-****-****-9999", "brand": "신한"},
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == owner_id


async def test_unknown_owner_is_400(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.post(
        "/api/v1/admin/cards",
        headers=headers,
        json={"user_id": 999999, "card_no_masked": "1234-****-****-0000", "brand": "신한"},
    )

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "INVALID_USER"
    assert body["field"] == "user_id"


async def test_card_with_transactions_cannot_be_deleted(client, seeded, login_as, db_session):
    """FK 위반이 500이 되면 Agent가 5xx를 재시도한다. 409로 변환돼야 한다."""
    headers = await login_as("admin@skon.example")
    owner = await make_user(db_session)
    card = await make_card(db_session, user=owner)
    await make_card_transaction(
        db_session, card=card, approved_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    )
    await db_session.commit()

    response = await client.delete(f"/api/v1/admin/cards/{card.id}", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HAS_DEPENDENTS"


async def test_card_without_transactions_can_be_deleted(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    owner = await make_user(db_session)
    card = await make_card(db_session, user=owner)
    card_id = card.id
    await db_session.commit()

    response = await client.delete(f"/api/v1/admin/cards/{card_id}", headers=headers)

    assert response.status_code == 204


async def test_deactivating_a_card_keeps_it_in_the_admin_list(
    client, seeded, login_as, db_session
):
    headers = await login_as("admin@skon.example")
    owner = await make_user(db_session)
    card = await make_card(db_session, user=owner)
    card_id = card.id
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/admin/cards/{card_id}", headers=headers, json={"is_active": False}
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    rows = (await client.get("/api/v1/admin/cards", headers=headers)).json()
    assert card_id in [row["id"] for row in rows]


async def test_missing_card_is_404(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.patch(
        "/api/v1/admin/cards/999999", headers=headers, json={"brand": "없음"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CARD_NOT_FOUND"
