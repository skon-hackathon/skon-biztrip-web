"""스코프 요구 표. 이 표가 유일한 권한 선언 지점이다."""

import pytest
from fastapi import Depends

from app.enums import ApiKeyScope
from app.errors import ForbiddenError
from app.services.api_scopes import (
    SCOPE_DESCRIPTIONS,
    SCOPE_REQUIREMENTS,
    required_scope_for,
    scope_catalog,
)


def test_read_endpoint_requires_read_scope():
    assert required_scope_for("GET", "/api/v1/trips") is ApiKeyScope.TRIPS_READ


def test_write_endpoint_requires_write_scope():
    assert required_scope_for("POST", "/api/v1/trips/{trip_id}/submit") is ApiKeyScope.TRIPS_WRITE


def test_master_data_endpoint_requires_no_scope():
    assert required_scope_for("GET", "/api/v1/codes") is None


def test_undeclared_route_is_rejected_not_allowed():
    """표에 없는 경로는 통과가 아니라 거부다. 여기서 통과시키면 신규 라우트가 전권이 된다."""
    with pytest.raises(ForbiddenError) as exc:
        required_scope_for("GET", "/api/v1/does-not-exist")
    assert exc.value.code == "SCOPE_UNDECLARED"


def test_method_matters():
    assert required_scope_for("GET", "/api/v1/trips") is ApiKeyScope.TRIPS_READ
    assert required_scope_for("POST", "/api/v1/trips") is ApiKeyScope.TRIPS_WRITE


def test_every_scope_has_a_description():
    assert set(SCOPE_DESCRIPTIONS) == set(ApiKeyScope)


def test_catalog_lists_endpoints_per_scope():
    catalog = {entry.scope: entry for entry in scope_catalog()}
    assert set(catalog) == set(ApiKeyScope)
    trips_read = catalog[ApiKeyScope.TRIPS_READ]
    assert "GET /api/v1/trips" in trips_read.endpoints
    assert "POST /api/v1/trips" not in trips_read.endpoints


def test_admin_scope_covers_every_admin_route():
    """Phase 5에서 /admin/*이 열렸다. 카탈로그가 그 경로 전부를 admin으로 보여줘야 한다.

    표에 admin 경로가 있는데 카탈로그가 다른 스코프로 묶으면 /developers 가이드가
    Agent에게 잘못된 스코프를 안내한다.
    """
    catalog = {entry.scope: entry for entry in scope_catalog()}
    admin_endpoints = catalog[ApiKeyScope.ADMIN].endpoints

    assert admin_endpoints, "admin 스코프에 엔드포인트가 하나도 없다"
    assert all(endpoint.split(" ", 1)[1].startswith("/api/v1/admin/") for endpoint in admin_endpoints)

    declared_admin_paths = {
        f"{method} {path}"
        for (method, path), scope in SCOPE_REQUIREMENTS.items()
        if path.startswith("/api/v1/admin/")
    }
    assert set(admin_endpoints) == declared_admin_paths


def test_table_has_no_duplicate_or_lowercase_methods():
    for method, path in SCOPE_REQUIREMENTS:
        assert method == method.upper()
        assert path.startswith("/api/v1/")


from fastapi import FastAPI

from app.deps import get_principal
from app.main import app as real_app
from app.services.api_scopes import assert_scope_table_complete


def test_real_app_passes_the_completeness_guard():
    assert_scope_table_complete(real_app)  # 예외가 없으면 성공


def test_guard_rejects_an_authenticated_route_missing_from_the_table():
    probe = FastAPI()

    @probe.get("/api/v1/unlisted")
    async def unlisted(user=Depends(get_principal)):  # noqa: B008
        return {}

    with pytest.raises(RuntimeError) as exc:
        assert_scope_table_complete(probe, requirements={})
    assert "GET /api/v1/unlisted" in str(exc.value)


def test_guard_ignores_routes_that_do_not_authenticate():
    """`/auth/login`·헬스체크처럼 get_principal을 안 쓰는 라우트는 스코프 개념이 없다."""
    probe = FastAPI()

    @probe.get("/api/v1/open")
    async def open_route():
        return {}

    assert_scope_table_complete(probe, requirements={})  # 예외 없음


def test_guard_rejects_a_table_entry_with_no_matching_route():
    """경로 이름을 바꾸고 표를 안 고치면 그 항목은 죽은 선언이 된다."""
    probe = FastAPI()

    @probe.get("/api/v1/auth/me")
    async def me(user=Depends(get_principal)):  # noqa: B008
        return {}

    with pytest.raises(RuntimeError) as exc:
        assert_scope_table_complete(
            probe,
            requirements={
                ("GET", "/api/v1/auth/me"): None,
                ("GET", "/api/v1/trips"): ApiKeyScope.TRIPS_READ,
            },
        )
    assert "GET /api/v1/trips" in str(exc.value)


def test_guard_rejects_an_app_with_no_authenticated_routes():
    """인증 라우트가 0개인데 표에 항목이 있으면 라우트 탐지가 깨진 것이다. 조용히 통과하면
    전 엔드포인트가 스코프 검사 없이 뜬다 — 가장 큰 사고가 가장 조용한 형태로 지나간다."""
    probe = FastAPI()

    @probe.get("/api/v1/open")
    async def open_route():
        return {}

    with pytest.raises(RuntimeError) as exc:
        assert_scope_table_complete(probe, requirements={("GET", "/api/v1/trips"): ApiKeyScope.TRIPS_READ})
    assert "GET /api/v1/trips" in str(exc.value)
