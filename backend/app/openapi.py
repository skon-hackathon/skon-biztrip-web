"""OpenAPI 스키마 보강.

FastAPI 기본 스키마에는 인증 방식과 필요 스코프가 없다. `/docs`만 보고 Agent를 붙일 수
있어야 하므로 두 가지를 주입한다.
1. securitySchemes 2종 (JWT / X-API-Key)
2. 각 오퍼레이션 설명에 필요 스코프 한 줄

설명은 `SCOPE_REQUIREMENTS`에서 뽑는다 — 손으로 적으면 표와 어긋난다.
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.services.api_scopes import SCOPE_REQUIREMENTS

_SECURITY_SCHEMES = {
    "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
    "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
}

_SECURITY = [{"BearerAuth": []}, {"ApiKeyAuth": []}]

#: JWT 전용 경로. API Key로는 열리지 않는다 (키가 키를 낳지 못하게).
_JWT_ONLY_PREFIX = "/api/v1/api-keys"

_DESCRIPTION = """\
SK온 출장시스템 데모 API.

**웹 UI와 외부 Agent가 물리적으로 같은 엔드포인트를 씁니다.** 화면에서 하는 일은
전부 이 API로 할 수 있습니다.

## 인증

- 브라우저: `Authorization: Bearer <JWT>` — 로그인 시 발급, 8시간 만료
- Agent: `X-API-Key: sk_live_...` — `/settings/api-keys`에서 발급, 키의 스코프만큼만 허용

두 헤더가 함께 오면 `X-API-Key`가 우선합니다.

## 에러

모든 에러 응답이 같은 모양입니다.

```json
{"error": {"code": "TRIP_INVALID_TRANSITION", "message": "...", "field": null}}
```

`code`는 기계가 읽는 도메인 코드입니다. 409의 `code`를 보고 재시도 여부를 판단하세요.
"""


def build_openapi(app: FastAPI):
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=_DESCRIPTION,
            routes=app.routes,
        )
        schema.setdefault("components", {})["securitySchemes"] = _SECURITY_SCHEMES

        for (method, path), scope in SCOPE_REQUIREMENTS.items():
            operation = schema.get("paths", {}).get(path, {}).get(method.lower())
            if operation is None:  # pragma: no cover - 소진 가드가 먼저 잡는다
                continue
            operation["security"] = _SECURITY
            if scope is None:
                note = "**스코프 불필요** — 인증만 하면 호출할 수 있습니다."
            else:
                note = f"**필요 스코프**: `{scope}`"
            if path.startswith(_JWT_ONLY_PREFIX):
                note = "**로그인 세션 전용** — API Key로는 호출할 수 없습니다."
            existing = operation.get("description", "")
            operation["description"] = f"{existing}\n\n{note}".strip()

        app.openapi_schema = schema
        return schema

    return custom_openapi
