"""/docs가 Agent 개발자에게 실제로 쓸모 있어야 한다."""


async def test_both_auth_schemes_are_documented(client):
    schema = (await client.get("/openapi.json")).json()
    schemes = schema["components"]["securitySchemes"]

    assert schemes["BearerAuth"] == {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    assert schemes["ApiKeyAuth"] == {"type": "apiKey", "in": "header", "name": "X-API-Key"}


async def test_protected_operations_declare_both_schemes(client):
    schema = (await client.get("/openapi.json")).json()
    operation = schema["paths"]["/api/v1/trips"]["get"]
    names = {name for entry in operation["security"] for name in entry}
    assert names == {"BearerAuth", "ApiKeyAuth"}


async def test_login_is_not_marked_as_protected(client):
    schema = (await client.get("/openapi.json")).json()
    assert "security" not in schema["paths"]["/api/v1/auth/login"]["post"]


async def test_required_scope_is_written_into_the_description(client):
    schema = (await client.get("/openapi.json")).json()
    assert "`trips:write`" in schema["paths"]["/api/v1/trips"]["post"]["description"]
    assert "`trips:read`" in schema["paths"]["/api/v1/trips"]["get"]["description"]


async def test_scopeless_endpoints_say_so(client):
    schema = (await client.get("/openapi.json")).json()
    assert "스코프 불필요" in schema["paths"]["/api/v1/codes"]["get"]["description"]


async def test_jwt_only_endpoints_are_marked(client):
    schema = (await client.get("/openapi.json")).json()
    description = schema["paths"]["/api/v1/api-keys"]["post"]["description"]
    assert "로그인 세션 전용" in description


async def test_jwt_only_endpoints_do_not_advertise_the_api_key_scheme(client):
    """설명 문구가 아니라 `security`에도 적혀야 한다.

    Agent는 스키마를 기계로 읽는다. 여기에 ApiKeyAuth가 남아 있으면 키로 호출해도 된다고
    믿고 403을 받는다 — 이 모듈이 존재하는 이유가 바로 그 독자다.
    """
    schema = (await client.get("/openapi.json")).json()
    for path in ("/api/v1/api-keys", "/api/v1/api-keys/{key_id}/revoke"):
        for operation in schema["paths"][path].values():
            names = {name for entry in operation["security"] for name in entry}
            assert names == {"BearerAuth"}, f"{path}: {names}"


async def test_password_endpoint_does_not_advertise_the_api_key_scheme(client):
    """스키마를 기계로 읽는 Agent가 키로 호출해도 된다고 믿으면 안 된다."""
    schema = (await client.get("/openapi.json")).json()
    operation = schema["paths"]["/api/v1/admin/users/{user_id}/password"]["post"]

    assert operation["security"] == [{"BearerAuth": []}]


async def test_admin_operations_declare_the_admin_scope(client):
    schema = (await client.get("/openapi.json")).json()
    operation = schema["paths"]["/api/v1/admin/users"]["get"]

    assert "admin" in operation["description"]
