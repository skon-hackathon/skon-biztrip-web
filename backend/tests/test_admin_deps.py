"""AdminUser는 역할을 본다. 스코프(키)는 SCOPE_REQUIREMENTS가 따로 본다 — 둘 다 필요하다."""

import httpx
import pytest
from fastapi import FastAPI

from app.db import get_db
from app.deps import AdminUser
from app.enums import ApiKeyScope, UserRole
from app.errors import register_error_handlers
from app.security import create_access_token
from app.services.api_scopes import SCOPE_REQUIREMENTS
from tests.factories import make_user


@pytest.fixture
def probe_app(db_session, monkeypatch):
    """AdminUser 하나만 붙은 최소 앱.

    경로를 SCOPE_REQUIREMENTS에 주입하는 이유: `_enforce_scope`는 JWT 요청에서도 표를 먼저
    조회하고, 표에 없으면 403 SCOPE_UNDECLARED를 던진다(의도된 fail-closed). 주입하지 않으면
    역할 검사에 도달하기 전에 스코프 검사에서 떨어져 이 테스트가 아무것도 검증하지 못한다.
    """
    monkeypatch.setitem(SCOPE_REQUIREMENTS, ("GET", "/probe"), ApiKeyScope.ADMIN)

    app = FastAPI()
    register_error_handlers(app)

    @app.get("/probe")
    async def probe(user: AdminUser) -> dict[str, str]:
        return {"name": user.name}

    app.dependency_overrides[get_db] = lambda: db_session
    return app


async def _call(app, headers: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/probe", headers=headers)


async def test_admin_passes(probe_app, db_session):
    admin = await make_user(db_session, role=UserRole.ADMIN, name="관리자")
    token = create_access_token(user_id=admin.id)

    response = await _call(probe_app, {"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"name": "관리자"}


async def test_manager_is_rejected(probe_app, db_session):
    manager = await make_user(db_session, role=UserRole.MANAGER)
    token = create_access_token(user_id=manager.id)

    response = await _call(probe_app, {"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_employee_is_rejected(probe_app, db_session):
    employee = await make_user(db_session, role=UserRole.EMPLOYEE)
    token = create_access_token(user_id=employee.id)

    response = await _call(probe_app, {"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
