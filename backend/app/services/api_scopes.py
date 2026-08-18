"""엔드포인트별 필요 스코프 선언 (spec 7 인증).

**이 표가 유일한 선언 지점이다.** 엔드포인트마다 `Depends(require_scope(...))`를 붙이는
방식을 쓰지 않는 이유는 상태전이에서 이미 배운 것과 같다 — 빠뜨릴 수 있는 검사는 언젠가
빠뜨리고, 그 실패는 fail-open이다. 여기서는 "스코프 의존성을 안 붙인 엔드포인트가
API Key에게 전권을 준다"가 된다.

표에 없는 경로는 통과가 아니라 403이며, `assert_scope_table_complete`가 임포트 시점에
표와 실제 라우트가 어긋나는 것을 잡는다.
"""

from dataclasses import dataclass

from app.enums import ApiKeyScope
from app.errors import ForbiddenError

_TR = ApiKeyScope.TRIPS_READ
_TW = ApiKeyScope.TRIPS_WRITE
_ER = ApiKeyScope.EXPENSES_READ
_EW = ApiKeyScope.EXPENSES_WRITE
_CR = ApiKeyScope.CARDS_READ
_AD = ApiKeyScope.ADMIN

#: (HTTP 메서드, FastAPI 라우트 경로) -> 필요 스코프. None은 "인증만 하면 됨".
#:
#: None을 쓰는 경로는 두 종류뿐이다.
#: 1. 마스터/참조 데이터 (`/codes` `/fund-centers` `/cost-centers`) — 모든 쓰기의 전제조건이고
#:    spec이 스코프를 6종으로 고정했으므로 별도 스코프를 만들지 않는다.
#: 2. 본인 리소스 (`/auth/me` `/notifications`).
#: 어느 쪽이든 **표에 명시적으로 적어야** 소진 가드를 통과한다. 빠뜨리면 기동이 실패한다.
#: 표와 라우터는 반드시 같은 커밋에서 움직인다 — 라우트 없는 표 항목도, 표에 없는 라우트도
#: 소진 가드가 거부한다.
SCOPE_REQUIREMENTS: dict[tuple[str, str], ApiKeyScope | None] = {
    ("GET", "/api/v1/auth/me"): None,
    ("GET", "/api/v1/codes"): None,
    ("GET", "/api/v1/codes/{group_code}"): None,
    ("GET", "/api/v1/fund-centers"): None,
    ("GET", "/api/v1/cost-centers"): None,
    ("GET", "/api/v1/api-keys"): None,
    ("POST", "/api/v1/api-keys"): None,
    ("POST", "/api/v1/api-keys/{key_id}/revoke"): None,
    ("GET", "/api/v1/scopes"): None,
    ("GET", "/api/v1/notifications"): None,
    ("POST", "/api/v1/notifications/{notification_id}/read"): None,
    ("GET", "/api/v1/trips"): _TR,
    ("POST", "/api/v1/trips"): _TW,
    ("GET", "/api/v1/trips/{trip_id}"): _TR,
    ("PATCH", "/api/v1/trips/{trip_id}"): _TW,
    ("DELETE", "/api/v1/trips/{trip_id}"): _TW,
    ("POST", "/api/v1/trips/{trip_id}/submit"): _TW,
    ("POST", "/api/v1/trips/{trip_id}/approve"): _TW,
    ("POST", "/api/v1/trips/{trip_id}/reject"): _TW,
    ("POST", "/api/v1/trips/{trip_id}/reopen"): _TW,
    ("POST", "/api/v1/trips/{trip_id}/complete"): _TW,
    ("GET", "/api/v1/trips/{trip_id}/timeline"): _TR,
    ("GET", "/api/v1/cards"): _CR,
    ("GET", "/api/v1/card-transactions"): _CR,
    ("GET", "/api/v1/expenses"): _ER,
    ("POST", "/api/v1/expenses"): _EW,
    ("GET", "/api/v1/expenses/{report_id}"): _ER,
    ("PATCH", "/api/v1/expenses/{report_id}"): _EW,
    ("GET", "/api/v1/expenses/{report_id}/match-candidates"): _ER,
    ("GET", "/api/v1/expenses/{report_id}/timeline"): _ER,
    ("POST", "/api/v1/expenses/{report_id}/items"): _EW,
    ("PATCH", "/api/v1/expense-items/{item_id}"): _EW,
    ("DELETE", "/api/v1/expense-items/{item_id}"): _EW,
    ("POST", "/api/v1/expenses/{report_id}/submit"): _EW,
    ("POST", "/api/v1/expenses/{report_id}/approve"): _EW,
    ("POST", "/api/v1/expenses/{report_id}/reject"): _EW,
    ("POST", "/api/v1/expenses/{report_id}/reopen"): _EW,
    ("GET", "/api/v1/admin/departments"): _AD,
    ("POST", "/api/v1/admin/departments"): _AD,
    ("PATCH", "/api/v1/admin/departments/{department_id}"): _AD,
    ("DELETE", "/api/v1/admin/departments/{department_id}"): _AD,
}

SCOPE_DESCRIPTIONS: dict[ApiKeyScope, str] = {
    ApiKeyScope.TRIPS_READ: "출장 조회 — 목록·상세·타임라인",
    ApiKeyScope.TRIPS_WRITE: "출장 쓰기 — 신청·수정·삭제·상신·결재·완료",
    ApiKeyScope.EXPENSES_READ: "정산 조회 — 목록·상세·매칭후보·타임라인",
    ApiKeyScope.EXPENSES_WRITE: "정산 쓰기 — 생성·항목 편집·제출·결재",
    ApiKeyScope.CARDS_READ: "법인카드 조회 — 카드 목록·카드거래",
    ApiKeyScope.ADMIN: "관리자 API (Phase 5에서 열림)",
}


@dataclass(frozen=True)
class ScopeCatalogEntry:
    scope: ApiKeyScope
    description: str
    endpoints: list[str]


def scope_catalog() -> list[ScopeCatalogEntry]:
    """스코프별 설명과 해당 엔드포인트. `/api/v1/scopes`와 `/developers` 가이드가 함께 쓴다.

    가이드를 손으로 적으면 표와 어긋난다. 같은 표에서 뽑아 어긋날 수 없게 한다.
    """
    grouped: dict[ApiKeyScope, list[str]] = {scope: [] for scope in ApiKeyScope}
    for (method, path), scope in SCOPE_REQUIREMENTS.items():
        if scope is not None:
            grouped[scope].append(f"{method} {path}")
    return [
        ScopeCatalogEntry(
            scope=scope,
            description=SCOPE_DESCRIPTIONS[scope],
            endpoints=sorted(grouped[scope]),
        )
        for scope in ApiKeyScope
    ]


def required_scope_for(method: str, path: str) -> ApiKeyScope | None:
    """이 엔드포인트에 필요한 스코프. 표에 없으면 **거부한다**.

    없으면 통과시키고 싶은 유혹이 있는데, 그러면 새 라우트가 스코프 선언 없이 배포됐을 때
    조용히 전권이 된다. 소진 가드가 있어 이 예외는 실전에서 발생하지 않아야 하지만,
    가드가 우회된 상황에서도 fail-closed로 남기려고 둔다.
    """
    key = (method.upper(), path)
    if key not in SCOPE_REQUIREMENTS:
        raise ForbiddenError(
            "SCOPE_UNDECLARED", "이 엔드포인트에 필요한 스코프가 선언되지 않았습니다"
        )
    return SCOPE_REQUIREMENTS[key]


def _authenticated_routes(app) -> set[tuple[str, str]]:
    """`get_principal`을 통과하는 (메서드, 경로) 전부.

    의존성 트리를 재귀로 훑는다 — `get_principal`이 직접 붙지 않고 `JwtOnlyUser`처럼
    한 겹 감싸서 붙는 경우가 있기 때문이다. 얕게만 보면 그런 라우트가 표 검사에서
    통째로 빠진다.

    라우트 순회도 `iter_route_contexts`를 거친다 — `include_router`로 등록된 라우트는
    `app.routes`에 곧바로 `APIRoute`로 나타나지 않고 `_IncludedRouter`로 감싸여 있어서,
    이 헬퍼로 펼쳐야 실제 라우트(및 그 `dependant`)가 보인다. 앱에 직접 등록한 라우트는
    감싸이지 않으므로 이 헬퍼가 그대로 통과시킨다.
    """
    from fastapi.routing import APIRoute, iter_route_contexts

    from app.deps import get_principal

    found: set[tuple[str, str]] = set()
    for route_context in iter_route_contexts(app.routes):
        if not isinstance(route_context.original_route, APIRoute):
            continue
        stack = list(route_context.dependant.dependencies)
        calls = set()
        while stack:
            dependency = stack.pop()
            if dependency.call is not None:
                calls.add(dependency.call)
            stack.extend(dependency.dependencies)
        if get_principal not in calls:
            continue
        for method in route_context.methods - {"HEAD", "OPTIONS"}:
            found.add((method, route_context.path))
    return found


def assert_scope_table_complete(
    app,
    requirements: dict[tuple[str, str], ApiKeyScope | None] = SCOPE_REQUIREMENTS,
) -> None:
    """표와 실제 라우트가 정확히 일치하는지 임포트 시점에 확인한다.

    양방향으로 본다. 라우트가 표에 없으면 스코프 미선언이고, 표에 있는데 라우트가 없으면
    경로 변경 후 죽은 선언이 남은 것이다. 후자를 방치하면 다음 사람이 그 항목을 보고
    "이 경로는 보호되고 있다"고 잘못 믿는다.

    `requirements` 기본값은 운영 표(`SCOPE_REQUIREMENTS`)다. 단위테스트가 작은 probe 앱을
    검사할 때 자기만의 작은 표를 넘길 수 있도록 열어둔 것일 뿐, 운영 경로에서 검사를
    느슨하게 만드는 용도가 아니다 — `app.main`은 인자 없이 호출해 항상 운영 표와 비교한다.
    인증 라우트가 0개인데 `requirements`에 항목이 있으면 그것도 어긋남이다: 라우트 탐지
    자체가 깨진 것일 수 있으므로 여기서 조용히 통과시키면 안 된다.
    """
    routes = _authenticated_routes(app)
    declared = set(requirements)
    missing = routes - declared
    extra = declared - routes
    if missing or extra:
        raise RuntimeError(
            "SCOPE_REQUIREMENTS가 실제 라우트와 어긋납니다. "
            f"표에 없는 라우트={sorted(f'{m} {p}' for m, p in missing)} "
            f"라우트가 없는 표 항목={sorted(f'{m} {p}' for m, p in extra)}"
        )
