"""API Key 관리 엔드포인트. 로그인 세션 전용이다."""

from app.enums import ApiKeyScope
from tests.factories import make_api_key, make_user


async def test_issue_returns_the_plaintext_key_once(client, login_as, seeded):
    headers = await login_as("user1@skon.example")

    created = await client.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "내 에이전트", "scopes": ["trips:read", "trips:write"]},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["key"].startswith("sk_live_")
    assert body["scopes"] == ["trips:read", "trips:write"]
    assert body["state"] == "ACTIVE"

    listed = await client.get("/api/v1/api-keys", headers=headers)
    assert listed.status_code == 200
    row = next(item for item in listed.json() if item["id"] == body["id"])
    assert "key" not in row  # 평문은 목록에 절대 없다
    assert row["key_prefix"] == body["key_prefix"]


async def test_issued_key_works_on_the_same_endpoints(client, login_as, seeded):
    headers = await login_as("user1@skon.example")
    created = await client.post(
        "/api/v1/api-keys", headers=headers, json={"name": "키", "scopes": ["trips:read"]}
    )
    raw = created.json()["key"]

    response = await client.get("/api/v1/trips", headers={"X-API-Key": raw})

    assert response.status_code == 200


async def test_unknown_scope_is_400_with_field(client, login_as, seeded):
    headers = await login_as("user1@skon.example")
    response = await client.post(
        "/api/v1/api-keys", headers=headers, json={"name": "키", "scopes": ["trips:delete"]}
    )
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "INVALID_SCOPE"
    assert body["field"] == "scopes"


async def test_revoke_kills_the_key(client, login_as, seeded):
    headers = await login_as("user1@skon.example")
    created = await client.post(
        "/api/v1/api-keys", headers=headers, json={"name": "키", "scopes": ["trips:read"]}
    )
    body = created.json()

    revoked = await client.post(f"/api/v1/api-keys/{body['id']}/revoke", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["state"] == "REVOKED"

    denied = await client.get("/api/v1/trips", headers={"X-API-Key": body["key"]})
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "API_KEY_REVOKED"


async def test_cannot_see_or_revoke_someone_elses_key(client, db_session, login_as, seeded):
    other = await make_user(db_session, name="남")
    _, key = await make_api_key(db_session, user=other, scopes=[ApiKeyScope.TRIPS_READ])
    headers = await login_as("user1@skon.example")

    listed = await client.get("/api/v1/api-keys", headers=headers)
    assert all(item["id"] != key.id for item in listed.json())

    response = await client.post(f"/api/v1/api-keys/{key.id}/revoke", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "API_KEY_NOT_FOUND"


async def test_an_api_key_cannot_mint_another_key(client, db_session, seeded):
    """키 세탁 방지 — cards:read 키 하나로 전권 키를 찍어낼 수 있으면 스코프가 무의미하다."""
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.TRIPS_WRITE])

    response = await client.post(
        "/api/v1/api-keys",
        headers={"X-API-Key": raw},
        json={"name": "탈취", "scopes": ["trips:read"]},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "API_KEY_FORBIDDEN"


async def test_an_api_key_cannot_list_keys(client, db_session, seeded):
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ])
    response = await client.get("/api/v1/api-keys", headers={"X-API-Key": raw})
    assert response.status_code == 403


async def test_expiry_days_out_of_range_is_422(client, login_as, seeded):
    headers = await login_as("user1@skon.example")
    response = await client.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "키", "scopes": ["trips:read"], "expires_in_days": 400},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SCHEMA_INVALID"
