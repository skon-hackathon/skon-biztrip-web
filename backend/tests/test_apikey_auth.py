"""X-API-Key 인증 경로. 웹과 같은 엔드포인트를 키로 호출할 수 있어야 한다."""

from datetime import datetime, timedelta, timezone

from app.enums import ApiKeyScope
from tests.factories import make_api_key, make_user


async def test_api_key_can_call_the_same_endpoint_as_the_browser(client, db_session, seeded):
    user = await make_user(db_session, name="에이전트")
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ])

    response = await client.get("/api/v1/trips", headers={"X-API-Key": raw})

    assert response.status_code == 200
    assert "items" in response.json()


async def test_api_key_identifies_its_owner(client, db_session, seeded):
    user = await make_user(db_session, name="키주인")
    raw, _ = await make_api_key(db_session, user=user)

    response = await client.get("/api/v1/auth/me", headers={"X-API-Key": raw})

    assert response.status_code == 200
    assert response.json()["name"] == "키주인"


async def test_missing_credentials_are_401(client, seeded):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_CREDENTIALS"


async def test_unknown_api_key_is_401(client, seeded):
    response = await client.get("/api/v1/auth/me", headers={"X-API-Key": "sk_live_" + "0" * 32})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


async def test_revoked_api_key_is_401(client, db_session, seeded):
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, revoked_at=datetime.now(timezone.utc))
    response = await client.get("/api/v1/auth/me", headers={"X-API-Key": raw})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "API_KEY_REVOKED"


async def test_expired_api_key_is_401(client, db_session, seeded):
    user = await make_user(db_session)
    raw, _ = await make_api_key(
        db_session, user=user, expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    response = await client.get("/api/v1/auth/me", headers={"X-API-Key": raw})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "API_KEY_EXPIRED"


async def test_api_key_wins_when_both_headers_are_present(client, db_session, login_as, seeded):
    """브라우저는 항상 Authorization을 보낸다. 명시적으로 얹은 키가 이긴다 — 결정적이어야 한다."""
    key_owner = await make_user(db_session, name="키주인")
    raw, _ = await make_api_key(db_session, user=key_owner)
    headers = await login_as("user1@skon.example")
    headers["X-API-Key"] = raw

    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["name"] == "키주인"


async def test_last_used_at_is_persisted_across_requests(client, db_session, seeded):
    user = await make_user(db_session)
    raw, key = await make_api_key(db_session, user=user)

    await client.get("/api/v1/auth/me", headers={"X-API-Key": raw})
    await db_session.refresh(key)

    assert key.last_used_at is not None
