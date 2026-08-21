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


#: 코드값은 전부 app/seed.py의 CODE_GROUPS에 실재하는 값이다. purpose_code에 "MEETING"
#: 같은 없는 값을 넣으면 400 INVALID_CODE가 나서 인증 테스트가 엉뚱한 이유로 깨진다.
TRIP_PAYLOAD = {
    "title": "울산 공장 점검",
    "purpose_code": "CUSTOMER",
    "purpose_detail": "라인 점검 및 협력사 미팅",
    "destination_type_code": "DOMESTIC",
    "country_code": "KR",
    "city": "울산",
    "start_date": "2026-09-01",
    "end_date": "2026-09-02",
}


async def _create_and_submit(client, headers) -> dict:
    created = await client.post("/api/v1/trips", headers=headers, json=TRIP_PAYLOAD)
    assert created.status_code == 201, created.text
    trip_id = created.json()["id"]
    submitted = await client.post(f"/api/v1/trips/{trip_id}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    return submitted.json()


async def test_jwt_and_api_key_produce_identical_results(client, db_session, login_as, seeded):
    """같은 사용자, 같은 엔드포인트, 두 인증 경로. 결과가 갈리면 안 된다."""
    jwt_headers = await login_as("user1@skon.example")

    from sqlalchemy import select

    from app.models import User

    user = (
        await db_session.execute(select(User).where(User.email == "user1@skon.example"))
    ).scalar_one()
    raw, _ = await make_api_key(
        db_session,
        user=user,
        scopes=[ApiKeyScope.TRIPS_READ, ApiKeyScope.TRIPS_WRITE],
    )
    key_headers = {"X-API-Key": raw}

    via_jwt = await _create_and_submit(client, jwt_headers)
    via_key = await _create_and_submit(client, key_headers)

    assert via_jwt["status"] == via_key["status"] == "SUBMITTED"
    assert via_jwt["title"] == via_key["title"]
    # 두 건 모두 같은 신청자로 기록된다
    assert via_jwt["user_id"] == via_key["user_id"]


async def test_timeline_is_recorded_for_the_api_key_path(client, db_session, login_as, seeded):
    """웹 경로로 들어오든 키 경로로 들어오든 이력이 누락될 수 없다 (spec 5.8)."""
    from sqlalchemy import select

    from app.models import User

    user = (
        await db_session.execute(select(User).where(User.email == "user1@skon.example"))
    ).scalar_one()
    raw, _ = await make_api_key(
        db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ, ApiKeyScope.TRIPS_WRITE]
    )
    headers = {"X-API-Key": raw}

    trip = await _create_and_submit(client, headers)
    timeline = await client.get(f"/api/v1/trips/{trip['id']}/timeline", headers=headers)

    assert timeline.status_code == 200
    assert [entry["action"] for entry in timeline.json()] == ["CREATED", "SUBMITTED"]


async def test_error_contract_is_identical_on_both_paths(client, db_session, login_as, seeded):
    """409 도메인 코드가 두 경로에서 같아야 Agent가 웹과 같은 판단을 할 수 있다."""
    from sqlalchemy import select

    from app.models import User

    user = (
        await db_session.execute(select(User).where(User.email == "user1@skon.example"))
    ).scalar_one()
    raw, _ = await make_api_key(
        db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ, ApiKeyScope.TRIPS_WRITE]
    )

    jwt_headers = await login_as("user1@skon.example")
    trip = await _create_and_submit(client, jwt_headers)

    for headers in (jwt_headers, {"X-API-Key": raw}):
        again = await client.post(f"/api/v1/trips/{trip['id']}/submit", headers=headers)
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "TRIP_INVALID_TRANSITION"
