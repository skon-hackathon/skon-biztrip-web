"""스코프 강제. 검사는 get_principal 안 한 곳에서만 일어난다."""

from app.enums import ApiKeyScope
from tests.factories import make_api_key, make_user


async def test_key_without_the_scope_is_403(client, db_session, seeded):
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.CARDS_READ])

    response = await client.get("/api/v1/trips", headers={"X-API-Key": raw})

    assert response.status_code == 403
    body = response.json()["error"]
    assert body["code"] == "SCOPE_REQUIRED"
    # Agent가 어떤 스코프를 붙여야 하는지 메시지만 보고 알 수 있어야 한다
    assert "trips:read" in body["message"]


async def test_read_scope_cannot_write(client, db_session, seeded):
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ])

    response = await client.post(
        "/api/v1/trips",
        headers={"X-API-Key": raw},
        json={
            "title": "스코프 테스트",
            "purpose_code": "CUSTOMER",
            "purpose_detail": "라인 점검",
            "destination_type_code": "DOMESTIC",
            "country_code": "KR",
            "city": "울산",
            "start_date": "2026-09-01",
            "end_date": "2026-09-02",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SCOPE_REQUIRED"


async def test_write_scope_does_not_imply_read(client, db_session, seeded):
    """쓰기가 읽기를 포함한다고 가정하지 않는다. 표에 적힌 것만 통과한다."""
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.TRIPS_WRITE])

    response = await client.get("/api/v1/trips", headers={"X-API-Key": raw})

    assert response.status_code == 403


async def test_scopeless_endpoint_passes_with_any_key(client, db_session, seeded):
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[])

    for path in ("/api/v1/auth/me", "/api/v1/codes", "/api/v1/fund-centers"):
        response = await client.get(path, headers={"X-API-Key": raw})
        assert response.status_code == 200, path


async def test_jwt_is_unrestricted(client, login_as, seeded):
    """JWT는 전 권한(role 범위 내)이다 — 스코프 개념이 적용되지 않는다."""
    headers = await login_as("user1@skon.example")
    for path in ("/api/v1/trips", "/api/v1/cards", "/api/v1/expenses"):
        response = await client.get(path, headers=headers)
        assert response.status_code == 200, path


async def test_role_check_still_applies_to_keys(client, db_session, seeded):
    """스코프는 권한을 **축소만** 한다. 키가 있다고 역할을 넘어설 수 없다."""
    from app.enums import TripStatus
    from tests.factories import make_trip

    owner = await make_user(db_session, name="신청자")
    trip = await make_trip(db_session, user=owner, status=TripStatus.SUBMITTED)
    stranger = await make_user(db_session, name="남")
    raw, _ = await make_api_key(db_session, user=stranger, scopes=[ApiKeyScope.TRIPS_WRITE])

    response = await client.post(f"/api/v1/trips/{trip.id}/approve", headers={"X-API-Key": raw})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRIP_NOT_FOUND"


async def test_empty_scope_key_is_not_unrestricted(client, db_session, seeded):
    """스코프가 빈 키는 '제한 없음'이 아니라 '아무 것도 못 함'이다."""
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[])
    response = await client.get("/api/v1/trips", headers={"X-API-Key": raw})
    assert response.status_code == 403


async def test_jwt_only_dependency_rejects_api_keys(db_session):
    """의존성 단위 테스트. 라우터는 Task 10에서 붙는다."""
    import pytest
    from fastapi import Request

    from app.deps import get_jwt_principal
    from app.errors import ForbiddenError

    request = Request({"type": "http", "method": "GET", "headers": [], "path": "/"})
    request.state.auth_method = "api_key"
    user = await make_user(db_session)

    with pytest.raises(ForbiddenError) as exc:
        await get_jwt_principal(request, user)
    assert exc.value.code == "API_KEY_FORBIDDEN"


async def test_jwt_only_dependency_accepts_jwt(db_session):
    from fastapi import Request

    from app.deps import get_jwt_principal

    request = Request({"type": "http", "method": "GET", "headers": [], "path": "/"})
    request.state.auth_method = "jwt"
    user = await make_user(db_session)

    assert await get_jwt_principal(request, user) is user


async def test_jwt_only_dependency_rejects_unknown_auth_method(db_session):
    """auth_method가 없으면 거부한다 — 모르면 막는 쪽이 기본값이다."""
    import pytest
    from fastapi import Request

    from app.deps import get_jwt_principal
    from app.errors import ForbiddenError

    request = Request({"type": "http", "method": "GET", "headers": [], "path": "/"})
    user = await make_user(db_session)

    with pytest.raises(ForbiddenError):
        await get_jwt_principal(request, user)
