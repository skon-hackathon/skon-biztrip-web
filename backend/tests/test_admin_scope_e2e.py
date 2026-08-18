"""Agent가 admin 스코프 키로 Admin API를 쓰는 경로. 웹과 같은 엔드포인트여야 한다."""

from sqlalchemy import select

from app.enums import ApiKeyScope, UserRole
from app.models import User
from tests.factories import make_api_key, make_user


async def _admin_user(db_session) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "admin@skon.example"))
    ).scalar_one()


async def test_admin_scope_key_can_create_a_department(client, seeded, db_session):
    admin = await _admin_user(db_session)
    raw, _ = await make_api_key(db_session, user=admin, scopes=[ApiKeyScope.ADMIN])
    await db_session.commit()

    response = await client.post(
        "/api/v1/admin/departments",
        headers={"X-API-Key": raw},
        json={"code": "D910", "name": "Agent가 만든 부서"},
    )

    assert response.status_code == 201


async def test_key_without_admin_scope_is_403(client, seeded, db_session):
    admin = await _admin_user(db_session)
    raw, _ = await make_api_key(db_session, user=admin, scopes=[ApiKeyScope.TRIPS_READ])
    await db_session.commit()

    response = await client.get("/api/v1/admin/departments", headers={"X-API-Key": raw})

    assert response.status_code == 403
    body = response.json()["error"]
    assert body["code"] == "SCOPE_REQUIRED"
    assert "admin" in body["message"]


async def test_admin_scope_key_owned_by_an_employee_is_403(client, seeded, db_session):
    """스코프는 권한을 **축소만** 한다. admin 스코프가 역할을 만들어주지는 않는다."""
    employee = await make_user(db_session, role=UserRole.EMPLOYEE)
    raw, _ = await make_api_key(db_session, user=employee, scopes=[ApiKeyScope.ADMIN])
    await db_session.commit()

    response = await client.get("/api/v1/admin/departments", headers={"X-API-Key": raw})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_scope_catalog_lists_admin_endpoints(client, seeded, login_as):
    """/developers 가이드가 이 응답을 그리므로, 표가 늘면 가이드가 저절로 따라온다."""
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/scopes", headers=headers)

    admin_entry = next(row for row in response.json() if row["scope"] == "admin")
    assert "GET /api/v1/admin/users" in admin_entry["endpoints"]
    assert "Phase 5" not in admin_entry["description"]
