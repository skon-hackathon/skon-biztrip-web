# Phase 3: 정산 — 카드내역·자동매칭·정산서·FC/CC 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 완료된 출장의 법인카드 사용내역을 자동매칭으로 끌어와 정산서를 만들고, 제출·결재까지 웹 UI와 API 양쪽에서 동일하게 수행할 수 있게 한다. 정산서가 승인되면 출장이 `SETTLED`로 자동 전이된다.

**Architecture:** Phase 2와 같은 3계층(`routers/` → `services/` → `models/`)을 유지한다. 자동매칭(`services/matching.py`)과 정산 도메인 규칙(`services/expense_rules.py`)은 DB를 모르는 순수 함수로 분리해 단위테스트로 전부 덮는다. 정산서 상태 전이는 출장과 똑같이 **전이표 + 주체표 + 임포트 시점 소진 가드** 구조를 쓴다. `COMPLETED → SETTLED`는 사용자 경로로는 절대 통과할 수 없고, 정산서 승인 서비스만 `assert_system_transition`으로 통과한다. 프론트엔드는 SvelteKit SPA에 `/cards` · `/expenses` · `/expenses/[id]` 세 화면을 추가한다.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · Pydantic v2 · pytest / SvelteKit 2 · Svelte 5 runes · TailwindCSS v4 · vitest

---

## 이 Phase가 만드는 것

| 영역 | 산출물 |
|---|---|
| API | `GET /cards`, `GET /card-transactions`, `GET·POST /expenses`, `GET·PATCH /expenses/{id}`, `GET /expenses/{id}/match-candidates`, `GET /expenses/{id}/timeline`, `POST /expenses/{id}/items`, `PATCH·DELETE /expense-items/{id}`, `POST /expenses/{id}/submit·approve·reject·reopen` |
| 화면 | `/cards`, `/expenses`, `/expenses/[id]`, 출장 상세의 정산 진입 버튼, 대시보드 "미정산" 카드 연결 |
| 도메인 | 자동매칭 순수 함수 + 매칭 사유, FC/CC 상속(coalesce), 정산서 전이표·주체표, `COMPLETED → SETTLED` 시스템 전이 |
| 이월 처리 | `load_active_codes` 정리, `assert_center_code` 순수 함수 추출 + `assert_fund_center`, `GET /fund-centers` 첫 소비처, 정산 액션의 `ActivityAction` 판단 |

## 이 Phase가 만들지 않는 것

- API Key 인증·스코프 검사 (`request.state.scopes`의 `UNRESTRICTED` 센티널 비교) — Phase 4
- Admin CRUD — Phase 5
- 744px 미만 반응형 붕괴 — 데스크톱 데모 우선
- 영수증 파일 업로드, 환율 재계산, 여비규정 한도 자동계산 — spec 9의 범위 밖
- 알림 뱃지 실시간 갱신(폴링·SSE) — 데모 범위 밖, Phase 2에서 내린 결정 유지

## 착수 전 확정한 설계 결정

이 결정들은 `docs/phase-status.md`의 "Phase 2에서 넘어온 항목"이 "먼저 정하고 시작할 것"이라고 지목한 것들이다. 구현 중에 다시 논의하지 말 것.

| # | 쟁점 | 결정 | 이유 |
|---|---|---|---|
| 1 | `COMPLETED → SETTLED`를 어떻게 통과시킬 것인가 | `trip_rules.assert_system_transition(current, target)`을 **새로 추가**한다. 기존 `assert_transition_allowed`는 그대로 SYSTEM 전이를 거부하고, 새 함수는 반대로 OWNER·APPROVER 전이를 거부한다 | 두 함수 모두 같은 `TRANSITION_ACTOR` 표를 읽으므로 표가 유일한 진실이다. 우회 경로(`assert_transition_allowed`를 건너뛰고 직접 status를 대입)를 열면 fail-open이 되풀이된다 |
| 2 | 정산서 승인 시 출장 이력 | `services/trips.py`의 `settle_trip_for_report`가 `record_transition`을 통과한다. commit은 호출자(정산 승인)가 한다 | 출장 타임라인이 `COMPLETED`에서 끊기면 안 된다. 한 트랜잭션 안에서 정산서 승인과 출장 전이가 함께 커밋돼야 한다 |
| 3 | 반려 후 흐름 | 출장과 동일하게 `REJECTED` 상태로 보내고 `POST /expenses/{id}/reopen`으로 `DRAFT`로 되돌린다 | spec 5.5는 "반려 시 DRAFT로 되돌린다"고 적었으나 `ExpenseReportStatus`에 `REJECTED`가 있고 `reject_reason` 컬럼도 있다. 즉시 DRAFT로 만들면 반려 사실이 화면에서 사라진다. Phase 2가 출장에서 내린 결정과 같은 모양 |
| 4 | 정산서 제출 시점의 출장 상태 | 생성은 `APPROVED`·`COMPLETED`에서 모두 가능(spec 5.5), **제출은 `COMPLETED`에서만** 가능 | 승인 시 `COMPLETED → SETTLED`가 성립해야 한다. 출장이 아직 `APPROVED`인데 정산서가 승인되면 전이표에 없는 `APPROVED → SETTLED`가 필요해진다. 제출 단계에서 막는 것이 결재자가 승인 버튼을 누른 뒤 409를 보는 것보다 낫다 |
| 5 | `ActivityAction`에 정산 전용 멤버를 추가할 것인가 | **추가하지 않는다.** `CREATED·UPDATED·SUBMITTED·APPROVED·REJECTED`를 `entity_type=EXPENSE_REPORT`로 구분해 쓴다 | 액션 이름은 이미 도메인 중립이다. `EXPENSE_SUBMITTED` 같은 멤버를 늘리면 타임라인 렌더러가 엔티티별로 갈라진다 |
| 6 | 정산서 승인 알림 | 정산서 쪽에서 `EXPENSE_APPROVED`를 신청자에게 보낸다. 출장 `SETTLED` 전이는 **알림 없이 activity_log만** 남긴다 | `NotificationType`에 `TRIP_SETTLED`가 없고, 한 번의 승인으로 알림 두 개를 받을 이유도 없다 |
| 7 | `load_active_codes` 이월 항목 | **삭제한다**(옵션 a). 딸린 테스트 3건도 함께 지우고, "그룹은 있는데 활성 코드가 0개" 규칙은 `validate_codes` 테스트로 옮긴다 | 생산 호출부가 없다. 두 벌의 쿼리 구현을 유지하는 비용이 규칙을 한 곳에 모으는 이익보다 크다. 오해를 부르는 "join은 두 경우를 구분하지 못한다" 주석도 함수와 함께 사라진다 |
| 8 | 금액 상한 | 항목은 `MAX_ITEM_AMOUNT = 9999999999.99`, 리포트 합계는 `MAX_REPORT_TOTAL = 999999999999.99`로 **서비스가** 막는다 | Phase 2 결함 #2와 같은 형태다. `Numeric(14,2)` 오버플로는 flush에서 500이 되고 Agent가 무한 재시도한다. 항목 상한만 두면 항목 여러 개로 합계를 넘길 수 있다 |
| 9 | 매칭 창의 날짜 기준 | `approved_at`을 **KST(Asia/Seoul)** 로 변환한 날짜로 비교한다 | 업무 날짜는 KST다. UTC로 비교하면 밤 9시 이후 결제가 하루 밀린다. 순수 함수라 `ZoneInfo`만 쓰고 DB·환경에 의존하지 않는다 |
| 10 | 총액 계산 | `total_amount_krw = sum(item.amount_krw for item if not item.is_excluded)`. 항목 추가·수정·삭제마다 서비스가 재계산 | `is_excluded`는 "후보로 끌어왔지만 정산에서 뺀다"는 뜻이므로 합계에서 빠져야 한다. 비정규화 컬럼의 책임자는 모델 주석대로 서비스다 |

## 설계에서 벗어나는 것 (기록용)

- **`PATCH /expenses/{id}` 추가.** spec 7 목록에 없지만 spec 5.5가 "cost_center_code는 출장에서 정산서로 승계되며 **수정 가능**하다"와 "제출 시 FC/CC가 비어 있으면 검증 실패"를 동시에 요구한다. 헤더 FC/CC를 고칠 경로가 없으면 FC가 빈 정산서는 영원히 제출할 수 없다.
- **`POST /expenses/{id}/reopen` 추가.** 결정 #3과 같은 이유. Phase 2의 `POST /trips/{id}/reopen`과 대칭이다.
- **`GET /expenses/{id}/timeline` 추가.** `activity_log`에 `entity_type=EXPENSE_REPORT`로 이미 쌓고 있는 이력을 노출한다. 없으면 쓰기만 하고 아무도 읽지 않는 테이블이 된다.

## 파일 구조

**백엔드 — 신규**

| 파일 | 책임 |
|---|---|
| `backend/app/services/matching.py` | 자동매칭 순수 함수. DB 접근 없음. 후보 산출 + 매칭 사유 + 비목 추천 |
| `backend/app/services/expense_rules.py` | 정산 도메인 순수 규칙 + 전이표 + 주체표 + `assert_expense_transition_allowed` |
| `backend/app/services/expenses.py` | 정산서 조회·목록·생성·수정·항목 CRUD·매칭 후보·전이 4종·타임라인 |
| `backend/app/services/cards.py` | 내 법인카드·카드거래 조회 |
| `backend/app/schemas/expense.py` | 정산서·항목·매칭후보 요청/응답 스키마 |
| `backend/app/schemas/card.py` | 카드·카드거래 응답 스키마 |
| `backend/app/routers/expenses.py` | 정산 HTTP 계층 |
| `backend/app/routers/cards.py` | 카드 HTTP 계층 |
| `backend/tests/test_matching.py` · `test_expense_rules.py` | 순수 함수 단위테스트 (DB 없음) |
| `backend/tests/test_cards_api.py` · `test_expenses_service_write.py` · `test_expenses_service_transitions.py` · `test_expenses_api.py` | 통합 테스트 |

**백엔드 — 수정**

- `backend/app/services/codes.py` — `load_active_codes` 삭제
- `backend/app/services/centers.py` — `assert_center_code` 순수 함수 추출, `assert_fund_center` 추가
- `backend/app/services/trip_rules.py` — `assert_system_transition` 추가
- `backend/app/services/trips.py` — `settle_trip_for_report` 추가
- `backend/app/services/numbering.py` — `next_report_no` 추가
- `backend/app/main.py` — 라우터 2개 등록
- `backend/tests/factories.py` — `make_card` · `make_card_transaction` · `make_expense_report` · `make_expense_item` 추가
- `backend/tests/test_codes_service.py` · `test_centers_service.py` · `test_trip_rules.py` · `test_numbering.py` — 위 변경에 맞춰 갱신

**프론트엔드 — 신규**

| 파일 | 책임 |
|---|---|
| `frontend/src/lib/api/cards.ts` · `expenses.ts` | API 호출부 + 쿼리스트링 빌더(순수, 테스트 대상) |
| `frontend/src/lib/expenses.ts` | 상태 라벨·톤, FC/CC 상속 해석, 합계 계산 (순수, 테스트 대상) |
| `frontend/src/lib/expenses.test.ts` · `frontend/src/lib/api/expenses.test.ts` | vitest |
| `frontend/src/lib/components/ExpenseStatusBadge.svelte` | 정산 상태 뱃지 |
| `frontend/src/lib/components/MatchPanel.svelte` | 자동매칭 후보 패널 (사유 + 담기) |
| `frontend/src/lib/components/ExpenseItemsTable.svelte` | 항목 테이블 (비목·금액·부서지정·제외) |
| `frontend/src/lib/components/CardTransactionTable.svelte` | 카드거래 표 |
| `frontend/src/routes/cards/+page.svelte` · `expenses/+page.svelte` · `expenses/[id]/+page.svelte` | 화면 |

**프론트엔드 — 수정**

- `frontend/src/lib/api/types.ts` — 카드·정산 타입 추가
- `frontend/src/routes/trips/[id]/+page.svelte` — "정산은 Phase 3에서 연결됩니다" 자리를 정산서 생성/이동 버튼으로 교체
- `frontend/src/routes/+page.svelte` — 미정산 카드의 "정산은 Phase 3" 뱃지 제거, `/expenses`로 연결
- `frontend/src/lib/components/AppShell.svelte` — 우측 블록에 `/cards` 링크 (가운데 3-탭은 DESIGN.md 규칙이라 건드리지 않는다)

**문서 — 수정**

- `docs/phase-status.md` · `CLAUDE.md` · `README.md`

---

## Task 1: `load_active_codes` 삭제 (이월 항목 정리)

**Files:**
- Modify: `backend/app/services/codes.py:26-46`
- Test: `backend/tests/test_codes_service.py`

- [ ] **Step 1: 삭제 대상 테스트 3건을 찾는다**

Run: `cd backend && grep -n "load_active_codes" -r app tests`

Expected: `app/services/codes.py`의 정의 1곳과 `tests/test_codes_service.py`의 테스트 3건만 나온다. 생산 코드 호출부가 나오면 삭제하지 말고 멈춘다.

- [ ] **Step 2: "그룹은 있는데 활성 코드가 0개" 규칙을 `validate_codes` 테스트로 옮긴다**

`backend/tests/test_codes_service.py`에 추가:

```python
async def test_validate_codes_rejects_value_when_group_has_no_active_codes(db_session):
    """그룹은 존재하지만 활성 코드가 0개면 UNKNOWN_CODE_GROUP이 아니라 INVALID_CODE다.

    두 경우를 구분하는 것이 이 프로젝트의 규칙이다 — 설정 오류(그룹 없음)와 사용자
    오타(값 오류)는 Agent가 다르게 대응해야 한다.
    """
    group = await make_code_group(db_session, "EMPTY_GROUP", [])
    assert group.id is not None

    with pytest.raises(ValidationError) as excinfo:
        await validate_codes(db_session, [("EMPTY_GROUP", "some_field", "ANY")])

    assert excinfo.value.code == "INVALID_CODE"
    assert excinfo.value.field == "some_field"
```

- [ ] **Step 3: 테스트를 돌려 통과를 확인한다 (아직 삭제 전)**

Run: `cd backend && uv run pytest tests/test_codes_service.py -v`
Expected: PASS (새 테스트 포함 전부)

- [ ] **Step 4: `load_active_codes`와 딸린 테스트 3건을 지운다**

`backend/app/services/codes.py`에서 `load_active_codes` 함수 전체(26–46행)를 삭제한다. `assert_valid_code`는 `validate_codes`가 쓰므로 **남긴다**.

`backend/tests/test_codes_service.py`에서 `load_active_codes`를 부르는 테스트 3건과 그 import를 삭제한다.

- [ ] **Step 5: 편집이 실제로 반영됐는지 grep으로 확인한다**

Run: `cd backend && grep -rn "load_active_codes" app tests | wc -l`
Expected: `0`

- [ ] **Step 6: 전체 테스트를 돌린다**

Run: `cd backend && uv run pytest -q`
Expected: 전부 PASS (건수는 3건 줄고 1건 늘어 291건 근처)

- [ ] **Step 7: 커밋**

```bash
git add backend/app/services/codes.py backend/tests/test_codes_service.py
git commit -m "refactor: drop unused load_active_codes and move its rule into validate_codes tests"
```

---

## Task 2: `assert_center_code` 순수 함수 추출 + `assert_fund_center`

**Files:**
- Modify: `backend/app/services/centers.py`
- Test: `backend/tests/test_centers_service.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_centers_service.py`에 추가:

```python
import pytest

from app.errors import ValidationError
from app.models import FundCenter
from app.services.centers import assert_center_code, assert_fund_center
from tests.factories import make_fund_center


def test_assert_center_code_passes_for_allowed_value():
    assert_center_code("CC2030", {"CC2030", "CC2040"}, code="INVALID_COST_CENTER", field="cost_center_code")


def test_assert_center_code_rejects_unknown_value():
    with pytest.raises(ValidationError) as excinfo:
        assert_center_code("CC9999", {"CC2030"}, code="INVALID_COST_CENTER", field="cost_center_code")
    assert excinfo.value.code == "INVALID_COST_CENTER"
    assert excinfo.value.field == "cost_center_code"


def test_assert_center_code_rejects_none():
    """None은 "미입력"이지 "허용됨"이 아니다. 집합에 None이 들어갈 일도 없다."""
    with pytest.raises(ValidationError):
        assert_center_code(None, {"FC1010"}, code="INVALID_FUND_CENTER", field="fund_center_code")


async def test_assert_fund_center_accepts_active_center(db_session):
    await make_fund_center(db_session, "FC9001")
    await assert_fund_center(db_session, "FC9001")


async def test_assert_fund_center_rejects_inactive_center(db_session):
    await make_fund_center(db_session, "FC9002", is_active=False)
    with pytest.raises(ValidationError) as excinfo:
        await assert_fund_center(db_session, "FC9002")
    assert excinfo.value.code == "INVALID_FUND_CENTER"
    assert excinfo.value.field == "fund_center_code"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_centers_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'assert_center_code'`

- [ ] **Step 3: 구현한다**

`backend/app/services/centers.py`의 `assert_cost_center`를 아래로 교체하고 두 함수를 추가한다:

```python
def assert_center_code(code: str | None, allowed: set[str], *, code_name: str, field: str) -> None:
    """순수 검증 — DB 접근 없음. 허용 집합은 호출자가 주입한다.

    `assert_fund_center`가 `assert_cost_center`의 `if code not in allowed: raise` 블록을
    복사하려는 순간에 뽑았다. 두 벌이 되면 한쪽만 고치는 날이 온다.
    """
    if code not in allowed:
        raise ValidationError(code_name, f"사용할 수 없는 센터입니다: {code}", field=field)


async def assert_cost_center(
    session: AsyncSession, code: str | None, *, field: str = "cost_center_code"
) -> None:
    allowed = await load_active_center_codes(session, CostCenter)
    assert_center_code(code, allowed, code_name="INVALID_COST_CENTER", field=field)


async def assert_fund_center(
    session: AsyncSession, code: str | None, *, field: str = "fund_center_code"
) -> None:
    allowed = await load_active_center_codes(session, FundCenter)
    assert_center_code(code, allowed, code_name="INVALID_FUND_CENTER", field=field)
```

`load_active_center_codes`의 docstring에서 "Phase 3의 전표 정산 쓰기 경로가 `assert_fund_center`를 추가할 때"로 시작하는 문장을 "`assert_cost_center`·`assert_fund_center` 양쪽이 쓴다"로 고친다 — 이제 예고가 아니라 사실이다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_centers_service.py -v`
Expected: PASS

기존 `assert_cost_center` 테스트의 메시지를 단언하고 있었다면 문구 변경("사용할 수 없는 코스트센터입니다" → "사용할 수 없는 센터입니다")에 맞춰 고친다. 에러 **코드**(`INVALID_COST_CENTER`)는 바뀌지 않았다.

- [ ] **Step 5: mutation으로 가드를 확인한다**

`assert_center_code`의 `if code not in allowed:`를 `if False:`로 바꾸고:

Run: `cd backend && uv run pytest tests/test_centers_service.py -q`
Expected: FAIL (최소 3건). 통과하면 테스트가 아무것도 지키지 않는 것이므로 되돌리고 테스트를 보강한다.

되돌린다: `git checkout backend/app/services/centers.py`가 아니라 손으로 `if False:`를 원래대로 고친다 (다른 편집이 함께 날아간다).

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/centers.py backend/tests/test_centers_service.py
git commit -m "refactor: extract assert_center_code and add assert_fund_center"
```

---

## Task 3: `assert_system_transition` — 시스템 전이 통로

**Files:**
- Modify: `backend/app/services/trip_rules.py:137-161`
- Test: `backend/tests/test_trip_rules.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_trip_rules.py`에 추가:

```python
from app.services.trip_rules import assert_system_transition


def test_assert_system_transition_allows_completed_to_settled():
    assert_system_transition(TripStatus.COMPLETED, TripStatus.SETTLED)


def test_assert_system_transition_rejects_owner_transition():
    """사용자 주체 전이를 시스템 통로로 우회할 수 없다.

    이 가드가 없으면 정산 서비스가 실수로 submit·complete를 호출자 검증 없이
    수행할 수 있는 통로가 열린다 — 그게 fail-open이다.
    """
    with pytest.raises(ForbiddenError) as excinfo:
        assert_system_transition(TripStatus.DRAFT, TripStatus.SUBMITTED)
    assert excinfo.value.code == "USER_TRANSITION_ONLY"


def test_assert_system_transition_rejects_approver_transition():
    with pytest.raises(ForbiddenError) as excinfo:
        assert_system_transition(TripStatus.SUBMITTED, TripStatus.APPROVED)
    assert excinfo.value.code == "USER_TRANSITION_ONLY"


def test_assert_system_transition_rejects_illegal_transition():
    """적법성을 권한보다 먼저 본다 — assert_transition_allowed와 순서를 맞춘다."""
    with pytest.raises(ConflictError) as excinfo:
        assert_system_transition(TripStatus.DRAFT, TripStatus.SETTLED)
    assert excinfo.value.code == "TRIP_INVALID_TRANSITION"


def test_user_path_still_rejects_the_system_transition():
    with pytest.raises(ForbiddenError) as excinfo:
        assert_transition_allowed(
            TripStatus.COMPLETED, TripStatus.SETTLED, user_id=1, owner_id=1, approver_id=2
        )
    assert excinfo.value.code == "SYSTEM_TRANSITION_ONLY"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_trip_rules.py -v`
Expected: FAIL — `ImportError: cannot import name 'assert_system_transition'`

- [ ] **Step 3: 구현한다**

`backend/app/services/trip_rules.py`의 파일 끝에 추가:

```python
def assert_system_transition(current: TripStatus, target: TripStatus) -> None:
    """시스템만 수행하는 전이를 검사한다 (지금은 COMPLETED → SETTLED 하나뿐).

    `assert_transition_allowed`와 **같은 표**를 읽는 것이 요점이다. 정산 서비스가
    표를 건너뛰고 `trip.status = SETTLED`를 직접 대입하면 적법성 검사도, 이력도
    없이 상태가 바뀐다. 그래서 시스템 경로에도 통로를 하나 만들어 주고, 그 통로가
    사용자 주체 전이는 거부하게 한다 — 두 방향 모두 fail-closed다.
    """
    assert_trip_transition(current, target)
    actor = TRANSITION_ACTOR[(current, target)]
    if actor is not TransitionActor.SYSTEM:
        raise ForbiddenError(
            "USER_TRANSITION_ONLY", "이 전이는 사용자가 수행해야 합니다"
        )
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_trip_rules.py -v`
Expected: PASS

- [ ] **Step 5: mutation으로 가드를 확인한다**

`if actor is not TransitionActor.SYSTEM:` → `if False:`로 바꾸고

Run: `cd backend && uv run pytest tests/test_trip_rules.py -q`
Expected: FAIL 2건 (`rejects_owner_transition`, `rejects_approver_transition`). 손으로 되돌린다.

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/trip_rules.py backend/tests/test_trip_rules.py
git commit -m "feat: add assert_system_transition for the COMPLETED -> SETTLED path"
```

---

## Task 4: 자동매칭 순수 함수 (`services/matching.py`)

DB를 모르는 함수다. 입력은 출장 기간 + 거래 뷰 리스트 + 제외할 거래 id 집합. `services/expenses.py`가 조회를 담당하고 이 모듈은 판정만 한다.

**Files:**
- Create: `backend/app/services/matching.py`
- Test: `backend/tests/test_matching.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_matching.py`:

```python
"""자동매칭 순수 함수 단위테스트. DB를 쓰지 않는다 (spec 8)."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.matching import (
    TransactionView,
    find_candidates,
    local_date,
    suggest_expense_category,
)

START = date(2026, 5, 10)
END = date(2026, 5, 12)


def txn(
    txn_id: int,
    *,
    when: datetime,
    category: str = "MEAL",
    amount: str = "30000",
    cancelled: bool = False,
) -> TransactionView:
    return TransactionView(
        id=txn_id,
        approved_at=when,
        merchant_category_code=category,
        amount_krw=Decimal(amount),
        is_cancelled=cancelled,
    )


def kst(day: date, hour: int) -> datetime:
    """KST 시각을 UTC datetime으로 변환한다 (KST = UTC+9)."""
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc) - timedelta(hours=9)


def test_local_date_uses_kst_not_utc():
    """UTC 22시는 KST로 다음 날 07시다. 업무 날짜는 KST 기준이다."""
    assert local_date(datetime(2026, 5, 10, 22, tzinfo=timezone.utc)) == date(2026, 5, 11)


def test_local_date_rejects_naive_datetime():
    with pytest.raises(ValueError):
        local_date(datetime(2026, 5, 10, 22))


def test_transaction_inside_the_trip_is_a_candidate():
    [candidate] = find_candidates(
        start_date=START, end_date=END, transactions=[txn(1, when=kst(date(2026, 5, 11), 12))]
    )
    assert candidate.transaction_id == 1
    assert "출장기간 내 승인" in candidate.reasons


def test_transaction_on_the_day_before_departure_is_a_candidate():
    [candidate] = find_candidates(
        start_date=START,
        end_date=END,
        transactions=[txn(1, when=kst(date(2026, 5, 9), 20), category="TRANSPORT")],
    )
    assert candidate.reasons == ("출발 전일 교통비",)


def test_non_transport_on_the_day_before_departure_keeps_the_generic_reason():
    [candidate] = find_candidates(
        start_date=START,
        end_date=END,
        transactions=[txn(1, when=kst(date(2026, 5, 9), 20), category="MEAL")],
    )
    assert candidate.reasons == ("출발 전일 승인",)


def test_transaction_on_the_day_after_return_is_a_candidate():
    [candidate] = find_candidates(
        start_date=START,
        end_date=END,
        transactions=[txn(1, when=kst(date(2026, 5, 13), 8), category="TRANSPORT")],
    )
    assert candidate.reasons == ("종료 익일 교통비",)


def test_lodging_inside_the_trip_gets_an_extra_reason():
    [candidate] = find_candidates(
        start_date=START,
        end_date=END,
        transactions=[txn(1, when=kst(date(2026, 5, 11), 21), category="LODGING")],
    )
    assert candidate.reasons == ("출장기간 내 승인", "출장기간 내 숙박")


def test_transaction_two_days_before_is_not_a_candidate():
    assert find_candidates(
        start_date=START, end_date=END, transactions=[txn(1, when=kst(date(2026, 5, 8), 12))]
    ) == []


def test_transaction_two_days_after_is_not_a_candidate():
    assert find_candidates(
        start_date=START, end_date=END, transactions=[txn(1, when=kst(date(2026, 5, 14), 12))]
    ) == []


def test_cancelled_transaction_is_not_a_candidate():
    assert find_candidates(
        start_date=START,
        end_date=END,
        transactions=[txn(1, when=kst(date(2026, 5, 11), 12), cancelled=True)],
    ) == []


def test_transaction_locked_by_another_submitted_report_is_not_a_candidate():
    assert find_candidates(
        start_date=START,
        end_date=END,
        transactions=[txn(1, when=kst(date(2026, 5, 11), 12))],
        excluded_transaction_ids=frozenset({1}),
    ) == []


def test_candidates_keep_a_deterministic_order():
    """승인 시각 오름차순, 같으면 id 오름차순. 화면과 API가 같은 순서를 보여야 한다."""
    result = find_candidates(
        start_date=START,
        end_date=END,
        transactions=[
            txn(3, when=kst(date(2026, 5, 12), 9)),
            txn(1, when=kst(date(2026, 5, 10), 9)),
            txn(2, when=kst(date(2026, 5, 10), 9)),
        ],
    )
    assert [candidate.transaction_id for candidate in result] == [1, 2, 3]


def test_suggested_category_maps_merchant_category():
    [candidate] = find_candidates(
        start_date=START,
        end_date=END,
        transactions=[txn(1, when=kst(date(2026, 5, 11), 12), category="LODGING")],
    )
    assert candidate.suggested_category_code == "LODGING"


def test_unknown_merchant_category_falls_back_to_etc():
    assert suggest_expense_category("SPACE_TRAVEL") == "ETC"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_matching.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.matching'`

- [ ] **Step 3: 구현한다**

`backend/app/services/matching.py`:

```python
"""자동매칭 규칙 (spec 5.6). DB 접근이 없는 순수 함수다.

입력은 출장 기간과 거래 뷰 리스트뿐이다. "누구의 카드인가"와 "다른 리포트가 이미
가져갔는가"는 조회가 필요하므로 `services/expenses.py`가 판단해서 걸러 넘긴다.
그렇게 나눠야 규칙 전체를 DB 없이 단위테스트할 수 있다.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

#: 업무 날짜는 KST 기준이다. UTC로 비교하면 밤 결제가 하루 밀린다.
KST = ZoneInfo("Asia/Seoul")

#: 카드 가맹점 업종(MERCHANT_CATEGORY) → 정산 비목(EXPENSE_CATEGORY) 추천.
#: 추천일 뿐이며 사용자가 바꿀 수 있다. 값 자체는 두 공통코드 그룹에 실재해야 한다.
MERCHANT_TO_EXPENSE: dict[str, str] = {
    "MEAL": "MEAL",
    "TRANSPORT": "TRANSPORT",
    "LODGING": "LODGING",
    "ENTERTAIN": "ENTERTAIN",
    "ETC": "ETC",
}
DEFAULT_EXPENSE_CATEGORY = "ETC"

#: 출장 전후로 며칠까지 후보로 볼 것인가 (spec 5.6: start - 1일 ~ end + 1일).
WINDOW_DAYS = 1


@dataclass(frozen=True)
class TransactionView:
    """매칭 판정에 필요한 거래 필드만 담는다. ORM 객체를 그대로 받지 않는 이유는
    이 모듈이 세션·lazy load에 얽히지 않게 하기 위해서다."""

    id: int
    approved_at: datetime
    merchant_category_code: str
    amount_krw: Decimal
    is_cancelled: bool


@dataclass(frozen=True)
class MatchCandidate:
    transaction_id: int
    reasons: tuple[str, ...]
    suggested_category_code: str


def local_date(moment: datetime) -> date:
    """timestamptz를 KST 날짜로 접는다.

    naive datetime을 조용히 UTC로 가정하지 않는다 — 그렇게 하면 DB 설정이 바뀌었을 때
    매칭 창이 9시간 밀리고 아무도 눈치채지 못한다.
    """
    if moment.tzinfo is None:
        raise ValueError("approved_at은 타임존을 가진 datetime이어야 합니다")
    return moment.astimezone(KST).date()


def suggest_expense_category(merchant_category_code: str) -> str:
    return MERCHANT_TO_EXPENSE.get(merchant_category_code, DEFAULT_EXPENSE_CATEGORY)


def _reasons(day: date, *, start_date: date, end_date: date, category: str) -> tuple[str, ...]:
    """매칭 사유는 UI와 API가 **같은 문자열**을 쓴다 (spec 5.6). 화면에서 따로 만들면
    Agent가 받는 설명과 사람이 보는 설명이 갈라진다."""
    if day < start_date:
        return ("출발 전일 교통비",) if category == "TRANSPORT" else ("출발 전일 승인",)
    if day > end_date:
        return ("종료 익일 교통비",) if category == "TRANSPORT" else ("종료 익일 승인",)
    if category == "LODGING":
        return ("출장기간 내 승인", "출장기간 내 숙박")
    return ("출장기간 내 승인",)


def find_candidates(
    *,
    start_date: date,
    end_date: date,
    transactions: list[TransactionView],
    excluded_transaction_ids: frozenset[int] = frozenset(),
) -> list[MatchCandidate]:
    """후보를 승인 시각 오름차순(같으면 id 오름차순)으로 돌려준다."""
    window_start = start_date - timedelta(days=WINDOW_DAYS)
    window_end = end_date + timedelta(days=WINDOW_DAYS)

    picked: list[tuple[datetime, int, MatchCandidate]] = []
    for transaction in transactions:
        if transaction.is_cancelled or transaction.id in excluded_transaction_ids:
            continue
        day = local_date(transaction.approved_at)
        if day < window_start or day > window_end:
            continue
        picked.append(
            (
                transaction.approved_at,
                transaction.id,
                MatchCandidate(
                    transaction_id=transaction.id,
                    reasons=_reasons(
                        day,
                        start_date=start_date,
                        end_date=end_date,
                        category=transaction.merchant_category_code,
                    ),
                    suggested_category_code=suggest_expense_category(
                        transaction.merchant_category_code
                    ),
                ),
            )
        )
    picked.sort(key=lambda row: (row[0], row[1]))
    return [candidate for _, _, candidate in picked]
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_matching.py -v`
Expected: PASS (15건)

- [ ] **Step 5: mutation으로 가드 3개를 확인한다**

하나씩 바꿔 돌리고 반드시 되돌린다:

| mutation | 기대 |
|---|---|
| `if transaction.is_cancelled or ...` → `if transaction.id in excluded_transaction_ids:` | `test_cancelled_transaction_is_not_a_candidate` FAIL |
| `... or transaction.id in excluded_transaction_ids` 제거 | `test_transaction_locked_by_another_submitted_report_is_not_a_candidate` FAIL |
| `WINDOW_DAYS = 1` → `2` | `test_transaction_two_days_before_is_not_a_candidate` FAIL |

Run(각각): `cd backend && uv run pytest tests/test_matching.py -q`

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/matching.py backend/tests/test_matching.py
git commit -m "feat: add pure auto-matching rules with match reasons"
```

---

## Task 5: 정산 도메인 순수 규칙 (`services/expense_rules.py`)

출장의 `trip_rules.py`와 **같은 구조**를 의도적으로 유지한다: 전이표 + 주체표 + 임포트 시점 소진 가드 + 단일 진입 함수.

**Files:**
- Create: `backend/app/services/expense_rules.py`
- Test: `backend/tests/test_expense_rules.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_expense_rules.py`:

```python
"""정산 순수 규칙 단위테스트. DB를 쓰지 않는다.

파생 데이터를 검사 대상 상수에서 만들지 않는다 — `set(ExpenseReportStatus) -
EXPENSE_EDITABLE_STATUSES` 같은 식으로 쓰면 상수를 넓히는 버그와 테스트가 함께 움직여
조용히 통과한다 (Phase 2 결함 #6). 리터럴로 적는다.
"""

from decimal import Decimal

import pytest

from app.enums import ExpenseReportStatus, TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, ValidationError
from app.services.expense_rules import (
    MAX_ITEM_AMOUNT,
    MAX_REPORT_TOTAL,
    assert_centers_present,
    assert_expense_transition_allowed,
    assert_has_items,
    assert_item_amount,
    assert_report_creatable,
    assert_report_editable,
    assert_report_total,
    assert_trip_completed,
    can_view_report,
    effective_center,
    sum_included,
)


@pytest.mark.parametrize("status", [ExpenseReportStatus.DRAFT, ExpenseReportStatus.REJECTED])
def test_editable_statuses(status):
    assert_report_editable(status)


@pytest.mark.parametrize("status", [ExpenseReportStatus.SUBMITTED, ExpenseReportStatus.APPROVED])
def test_non_editable_statuses(status):
    with pytest.raises(ConflictError) as excinfo:
        assert_report_editable(status)
    assert excinfo.value.code == "EXPENSE_NOT_EDITABLE"


@pytest.mark.parametrize("status", [TripStatus.APPROVED, TripStatus.COMPLETED])
def test_report_can_be_created_for_approved_and_completed_trips(status):
    assert_report_creatable(status)


@pytest.mark.parametrize(
    "status",
    [
        TripStatus.DRAFT,
        TripStatus.SUBMITTED,
        TripStatus.REJECTED,
        TripStatus.SETTLED,
    ],
)
def test_report_cannot_be_created_for_other_trip_statuses(status):
    with pytest.raises(ConflictError) as excinfo:
        assert_report_creatable(status)
    assert excinfo.value.code == "TRIP_NOT_REPORTABLE"


def test_submit_requires_a_completed_trip():
    """승인 시 COMPLETED → SETTLED가 성립해야 하므로 제출 단계에서 막는다."""
    assert_trip_completed(TripStatus.COMPLETED)
    with pytest.raises(ConflictError) as excinfo:
        assert_trip_completed(TripStatus.APPROVED)
    assert excinfo.value.code == "TRIP_NOT_COMPLETED"


def test_item_amount_bounds():
    assert_item_amount(Decimal("0"))
    assert_item_amount(MAX_ITEM_AMOUNT)
    with pytest.raises(ValidationError) as negative:
        assert_item_amount(Decimal("-1"))
    assert negative.value.code == "INVALID_AMOUNT"
    assert negative.value.field == "amount_krw"
    with pytest.raises(ValidationError) as too_big:
        assert_item_amount(MAX_ITEM_AMOUNT + Decimal("0.01"))
    assert too_big.value.code == "INVALID_AMOUNT"


def test_report_total_bound():
    """항목 상한만 두면 항목 여러 개로 합계를 넘길 수 있다. 그 오버플로는 flush에서
    500이 되고 Agent가 무한 재시도한다 (Phase 2 결함 #2와 같은 형태)."""
    assert_report_total(MAX_REPORT_TOTAL)
    with pytest.raises(ValidationError) as excinfo:
        assert_report_total(MAX_REPORT_TOTAL + Decimal("0.01"))
    assert excinfo.value.code == "TOTAL_AMOUNT_EXCEEDED"
    assert excinfo.value.field == "amount_krw"


def test_submit_requires_items():
    assert_has_items(1)
    with pytest.raises(ConflictError) as excinfo:
        assert_has_items(0)
    assert excinfo.value.code == "EXPENSE_NO_ITEMS"


def test_submit_requires_both_centers():
    assert_centers_present(fund_center_code="FC1010", cost_center_code="CC2030")
    with pytest.raises(ValidationError) as no_fund:
        assert_centers_present(fund_center_code=None, cost_center_code="CC2030")
    assert no_fund.value.code == "CENTER_REQUIRED"
    assert no_fund.value.field == "fund_center_code"
    with pytest.raises(ValidationError) as no_cost:
        assert_centers_present(fund_center_code="FC1010", cost_center_code="  ")
    assert no_cost.value.field == "cost_center_code"


def test_effective_center_falls_back_to_the_report_value():
    assert effective_center("CC2040", "CC2030") == "CC2040"
    assert effective_center(None, "CC2030") == "CC2030"
    assert effective_center(None, None) is None


def test_sum_included_skips_excluded_items():
    assert sum_included([(Decimal("100"), False), (Decimal("50"), True)]) == Decimal("100")
    assert sum_included([]) == Decimal("0")


def test_owner_and_approver_and_admin_can_view():
    assert can_view_report(user_id=1, role=UserRole.EMPLOYEE, owner_id=1, approver_id=2)
    assert can_view_report(user_id=2, role=UserRole.MANAGER, owner_id=1, approver_id=2)
    assert can_view_report(user_id=9, role=UserRole.ADMIN, owner_id=1, approver_id=2)
    assert not can_view_report(user_id=3, role=UserRole.EMPLOYEE, owner_id=1, approver_id=2)


def test_submit_is_owner_only():
    assert_expense_transition_allowed(
        ExpenseReportStatus.DRAFT,
        ExpenseReportStatus.SUBMITTED,
        user_id=1,
        owner_id=1,
        approver_id=2,
    )
    with pytest.raises(ForbiddenError) as excinfo:
        assert_expense_transition_allowed(
            ExpenseReportStatus.DRAFT,
            ExpenseReportStatus.SUBMITTED,
            user_id=2,
            owner_id=1,
            approver_id=2,
        )
    assert excinfo.value.code == "NOT_EXPENSE_OWNER"


def test_approve_is_approver_only():
    assert_expense_transition_allowed(
        ExpenseReportStatus.SUBMITTED,
        ExpenseReportStatus.APPROVED,
        user_id=2,
        owner_id=1,
        approver_id=2,
    )
    with pytest.raises(ForbiddenError) as excinfo:
        assert_expense_transition_allowed(
            ExpenseReportStatus.SUBMITTED,
            ExpenseReportStatus.APPROVED,
            user_id=1,
            owner_id=1,
            approver_id=2,
        )
    assert excinfo.value.code == "NOT_EXPENSE_APPROVER"


def test_illegal_transition_is_reported_before_the_actor_check():
    """결재자가 DRAFT 리포트를 승인하려 하면 409가 403보다 실질적인 답이다 —
    출장 쪽 assert_transition_allowed와 같은 순서다."""
    with pytest.raises(ConflictError) as excinfo:
        assert_expense_transition_allowed(
            ExpenseReportStatus.DRAFT,
            ExpenseReportStatus.APPROVED,
            user_id=2,
            owner_id=1,
            approver_id=2,
        )
    assert excinfo.value.code == "EXPENSE_INVALID_TRANSITION"


def test_reopen_is_owner_only():
    assert_expense_transition_allowed(
        ExpenseReportStatus.REJECTED,
        ExpenseReportStatus.DRAFT,
        user_id=1,
        owner_id=1,
        approver_id=2,
    )
    with pytest.raises(ForbiddenError):
        assert_expense_transition_allowed(
            ExpenseReportStatus.REJECTED,
            ExpenseReportStatus.DRAFT,
            user_id=2,
            owner_id=1,
            approver_id=2,
        )


def test_approved_report_is_terminal():
    with pytest.raises(ConflictError):
        assert_expense_transition_allowed(
            ExpenseReportStatus.APPROVED,
            ExpenseReportStatus.DRAFT,
            user_id=1,
            owner_id=1,
            approver_id=2,
        )
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_expense_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.expense_rules'`

- [ ] **Step 3: 구현한다**

`backend/app/services/expense_rules.py`:

```python
"""정산 도메인의 순수 규칙. DB 접근이 없어 단위테스트로 전부 덮는다.

출장(`trip_rules.py`)과 같은 구조를 일부러 유지한다 — 전이표와 주체표를 따로 두되
임포트 시점에 두 표의 키가 정확히 일치하는지 검사한다. Phase 2에서 가장 컸던 결함이
"적법성과 권한을 따로 부를 수 있게 열어둔 것"이었고, 그 실패는 fail-open이었다.
"""

from collections.abc import Iterable
from decimal import Decimal

from app.enums import ExpenseReportStatus, TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, ValidationError

# TransitionActor를 출장 쪽에서 가져다 쓴다. 주체의 종류(신청자·결재자·시스템)는
# 도메인 중립이며, 두 벌로 두면 "OWNER"가 두 개 존재하는 상태가 된다.
from app.services.trip_rules import TransitionActor

#: 항목을 고칠 수 있는 리포트 상태. 반려된 리포트는 고쳐서 reopen 후 재상신한다.
EXPENSE_EDITABLE_STATUSES = frozenset(
    {ExpenseReportStatus.DRAFT, ExpenseReportStatus.REJECTED}
)

#: 정산서를 만들 수 있는 출장 상태 (spec 5.5).
REPORTABLE_TRIP_STATUSES = frozenset({TripStatus.APPROVED, TripStatus.COMPLETED})

#: expense_item.amount_krw는 Numeric(14, 2)다. 항목 하나가 컬럼을 넘지 못하게 하되,
#: 합계 상한보다 두 자리 낮게 잡아 항목 몇 개로 합계를 넘기는 일이 흔하지 않게 한다.
MAX_ITEM_AMOUNT = Decimal("9999999999.99")

#: expense_report.total_amount_krw도 Numeric(14, 2)다. 항목 상한만으로는 못 막는다.
MAX_REPORT_TOTAL = Decimal("999999999999.99")


def can_view_report(
    *, user_id: int, role: UserRole, owner_id: int, approver_id: int | None
) -> bool:
    """신청자·결재자·ADMIN만 정산서를 볼 수 있다. False면 호출부는 403이 아니라 404다."""
    if role == UserRole.ADMIN:
        return True
    return user_id == owner_id or (approver_id is not None and user_id == approver_id)


def assert_report_owner(*, user_id: int, owner_id: int) -> None:
    if user_id != owner_id:
        raise ForbiddenError("NOT_EXPENSE_OWNER", "본인의 정산서만 처리할 수 있습니다")


def assert_report_approver(*, user_id: int, approver_id: int | None) -> None:
    if approver_id is None or user_id != approver_id:
        raise ForbiddenError("NOT_EXPENSE_APPROVER", "이 정산서의 결재자가 아닙니다")


def assert_report_editable(status: ExpenseReportStatus) -> None:
    if status not in EXPENSE_EDITABLE_STATUSES:
        raise ConflictError(
            "EXPENSE_NOT_EDITABLE", f"{status} 상태의 정산서는 수정할 수 없습니다"
        )


def assert_report_creatable(trip_status: TripStatus) -> None:
    if trip_status not in REPORTABLE_TRIP_STATUSES:
        raise ConflictError(
            "TRIP_NOT_REPORTABLE",
            f"{trip_status} 상태의 출장에는 정산서를 만들 수 없습니다",
        )


def assert_trip_completed(trip_status: TripStatus) -> None:
    """제출은 출장이 완료된 뒤에만 가능하다.

    정산서 승인이 출장의 COMPLETED → SETTLED를 트리거하므로, 출장이 아직 APPROVED면
    승인 시점에 전이표에 없는 APPROVED → SETTLED가 필요해진다. 결재자가 승인을 누른
    뒤 409를 보는 것보다 신청자가 제출에서 막히는 편이 낫다.
    """
    if trip_status is not TripStatus.COMPLETED:
        raise ConflictError(
            "TRIP_NOT_COMPLETED", "출장을 완료 처리한 뒤에 정산서를 제출할 수 있습니다"
        )


def assert_item_amount(amount: Decimal) -> None:
    if amount < 0:
        raise ValidationError("INVALID_AMOUNT", "금액은 0 이상이어야 합니다", field="amount_krw")
    if amount > MAX_ITEM_AMOUNT:
        raise ValidationError(
            "INVALID_AMOUNT", f"금액은 {MAX_ITEM_AMOUNT}를 넘을 수 없습니다", field="amount_krw"
        )


def assert_report_total(total: Decimal) -> None:
    if total > MAX_REPORT_TOTAL:
        raise ValidationError(
            "TOTAL_AMOUNT_EXCEEDED",
            f"정산 합계는 {MAX_REPORT_TOTAL}를 넘을 수 없습니다",
            field="amount_krw",
        )


def assert_has_items(item_count: int) -> None:
    if item_count <= 0:
        raise ConflictError("EXPENSE_NO_ITEMS", "정산 항목이 없어 제출할 수 없습니다")


def assert_centers_present(*, fund_center_code: str | None, cost_center_code: str | None) -> None:
    """제출 시 FC/CC가 비어 있으면 검증 실패다 (spec 5.5)."""
    if not (fund_center_code or "").strip():
        raise ValidationError(
            "CENTER_REQUIRED", "펀드센터를 지정해야 제출할 수 있습니다", field="fund_center_code"
        )
    if not (cost_center_code or "").strip():
        raise ValidationError(
            "CENTER_REQUIRED", "코스트센터를 지정해야 제출할 수 있습니다", field="cost_center_code"
        )


def effective_center(item_code: str | None, report_code: str | None) -> str | None:
    """FC/CC 계층의 coalesce (spec 5.5). 항목 값이 비면 리포트 값을 쓴다."""
    return item_code if item_code is not None else report_code


def sum_included(amounts: Iterable[tuple[Decimal, bool]]) -> Decimal:
    """(금액, is_excluded) 쌍의 합. 제외된 항목은 합계에서 뺀다."""
    return sum((amount for amount, excluded in amounts if not excluded), Decimal("0"))


EXPENSE_ALLOWED_TRANSITIONS: dict[ExpenseReportStatus, frozenset[ExpenseReportStatus]] = {
    ExpenseReportStatus.DRAFT: frozenset({ExpenseReportStatus.SUBMITTED}),
    ExpenseReportStatus.SUBMITTED: frozenset(
        {ExpenseReportStatus.APPROVED, ExpenseReportStatus.REJECTED}
    ),
    ExpenseReportStatus.REJECTED: frozenset({ExpenseReportStatus.DRAFT}),
    ExpenseReportStatus.APPROVED: frozenset(),
}

_missing_statuses = set(ExpenseReportStatus) - set(EXPENSE_ALLOWED_TRANSITIONS)
if _missing_statuses:
    raise RuntimeError(f"EXPENSE_ALLOWED_TRANSITIONS missing entries for {_missing_statuses}")

#: 각 전이의 수행 주체. 아래 가드가 EXPENSE_ALLOWED_TRANSITIONS와의 일치를 임포트
#: 시점에 강제한다 — 전이를 추가하고 주체를 빠뜨리면 조용히 "아무나 가능"이 되는 게
#: 아니라 임포트가 깨진다.
EXPENSE_TRANSITION_ACTOR: dict[
    tuple[ExpenseReportStatus, ExpenseReportStatus], TransitionActor
] = {
    (ExpenseReportStatus.DRAFT, ExpenseReportStatus.SUBMITTED): TransitionActor.OWNER,
    (ExpenseReportStatus.SUBMITTED, ExpenseReportStatus.APPROVED): TransitionActor.APPROVER,
    (ExpenseReportStatus.SUBMITTED, ExpenseReportStatus.REJECTED): TransitionActor.APPROVER,
    (ExpenseReportStatus.REJECTED, ExpenseReportStatus.DRAFT): TransitionActor.OWNER,
}

_all_expense_transitions = {
    (current, target)
    for current, targets in EXPENSE_ALLOWED_TRANSITIONS.items()
    for target in targets
}
_missing_actors = _all_expense_transitions - set(EXPENSE_TRANSITION_ACTOR)
_extra_actors = set(EXPENSE_TRANSITION_ACTOR) - _all_expense_transitions
if _missing_actors or _extra_actors:
    raise RuntimeError(
        "EXPENSE_TRANSITION_ACTOR가 EXPENSE_ALLOWED_TRANSITIONS와 어긋납니다: "
        f"missing={_missing_actors} extra={_extra_actors}"
    )


def assert_expense_transition_allowed(
    current: ExpenseReportStatus,
    target: ExpenseReportStatus,
    *,
    user_id: int,
    owner_id: int,
    approver_id: int | None,
) -> None:
    """정산서 전이의 적법성과 수행 주체를 한 번에 검사한다. 호출부는 이것만 부른다."""
    if target not in EXPENSE_ALLOWED_TRANSITIONS[current]:
        raise ConflictError(
            "EXPENSE_INVALID_TRANSITION", f"{current} 상태에서 {target} 로 변경할 수 없습니다"
        )
    actor = EXPENSE_TRANSITION_ACTOR[(current, target)]
    if actor is TransitionActor.OWNER:
        assert_report_owner(user_id=user_id, owner_id=owner_id)
    elif actor is TransitionActor.APPROVER:
        assert_report_approver(user_id=user_id, approver_id=approver_id)
    else:  # pragma: no cover - 정산에는 시스템 전이가 없다
        raise ForbiddenError("SYSTEM_TRANSITION_ONLY", "이 전이는 시스템에 의해서만 수행됩니다")
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_expense_rules.py -v`
Expected: PASS

- [ ] **Step 5: 소진 가드가 실제로 무는지 확인한다**

`EXPENSE_TRANSITION_ACTOR`에서 `(REJECTED, DRAFT)` 줄을 잠시 지우고:

Run: `cd backend && uv run pytest tests/test_expense_rules.py -q`
Expected: **컬렉션 단계에서** `RuntimeError: EXPENSE_TRANSITION_ACTOR가 ... 어긋납니다: missing={...}`. 손으로 되돌린다.

- [ ] **Step 6: 금액 가드 mutation**

`assert_report_total`의 `if total > MAX_REPORT_TOTAL:` → `if False:`

Run: `cd backend && uv run pytest tests/test_expense_rules.py -q`
Expected: FAIL 1건. 되돌린다.

- [ ] **Step 7: 커밋**

```bash
git add backend/app/services/expense_rules.py backend/tests/test_expense_rules.py
git commit -m "feat: add pure expense rules with transition and actor tables"
```

---

## Task 6: 정산서 채번 `next_report_no`

**Files:**
- Modify: `backend/app/services/numbering.py`
- Test: `backend/tests/test_numbering.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_numbering.py`에 추가:

```python
from app.services.numbering import next_report_no


async def test_next_report_no_starts_at_one(db_session):
    assert await next_report_no(db_session, date(2031, 3, 4)) == "EX-2031-0001"


async def test_next_report_no_continues_from_the_max_of_the_same_year(db_session, seeded):
    """시드가 EX-2026-0001..0012를 만든다. 다음은 0013이다."""
    assert await next_report_no(seeded, date(2026, 3, 4)) == "EX-2026-0013"


async def test_next_report_no_is_scoped_per_year(db_session, seeded):
    assert await next_report_no(seeded, date(2027, 1, 1)) == "EX-2027-0001"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_numbering.py -v`
Expected: FAIL — `ImportError: cannot import name 'next_report_no'`

- [ ] **Step 3: 구현한다**

`backend/app/services/numbering.py`에 추가 (`Trip`과 함께 `ExpenseReport`를 import한다):

```python
async def next_report_no(session: AsyncSession, today: date) -> str:
    """`EX-YYYY-NNNN`. 연도별로 0001부터 다시 센다.

    `next_trip_no`와 같은 max() + 1 방식이고 같은 한계를 갖는다 — 단일 인스턴스 전제,
    마지막 방어선은 `expense_report.report_no`의 unique 제약이다.
    """
    prefix = f"EX-{today.year}-"
    last = (
        await session.execute(
            select(func.max(ExpenseReport.report_no)).where(
                ExpenseReport.report_no.like(f"{prefix}%")
            )
        )
    ).scalar_one_or_none()
    sequence = int(last[len(prefix) :]) + 1 if last else 1
    return f"{prefix}{sequence:04d}"
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_numbering.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/numbering.py backend/tests/test_numbering.py
git commit -m "feat: add expense report numbering"
```

---

## Task 7: 카드·정산 스키마

**Files:**
- Create: `backend/app/schemas/card.py`, `backend/app/schemas/expense.py`

- [ ] **Step 1: 카드 스키마를 만든다**

`backend/app/schemas/card.py`:

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_no_masked: str
    brand: str
    is_active: bool


class CardTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    approved_at: datetime
    merchant_name: str
    merchant_category_code: str
    amount: Decimal
    currency_code: str
    amount_krw: Decimal
    is_cancelled: bool
```

- [ ] **Step 2: 정산 스키마를 만든다**

`backend/app/schemas/expense.py`:

```python
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.enums import ExpenseReportStatus


class ExpenseReportCreate(BaseModel):
    trip_id: int


class ExpenseReportUpdate(BaseModel):
    """헤더 FC/CC 수정. spec 5.5의 "승계되며 수정 가능하다"를 만족시키는 유일한 경로다."""

    fund_center_code: str | None = Field(default=None, min_length=1, max_length=20)
    cost_center_code: str | None = Field(default=None, min_length=1, max_length=20)


class ExpenseItemCreate(BaseModel):
    # 카드거래를 연결하면 amount_krw를 생략할 수 있다 — 거래 금액을 그대로 쓴다.
    # 수기 항목(card_transaction_id=None)은 금액이 필수이며 서비스가 400으로 막는다.
    card_transaction_id: int | None = None
    expense_category_code: str = Field(min_length=1, max_length=40)
    amount_krw: Decimal | None = None
    memo: str | None = Field(default=None, max_length=255)
    fund_center_code: str | None = Field(default=None, min_length=1, max_length=20)
    cost_center_code: str | None = Field(default=None, min_length=1, max_length=20)


class ExpenseItemUpdate(BaseModel):
    expense_category_code: str | None = Field(default=None, min_length=1, max_length=40)
    amount_krw: Decimal | None = None
    memo: str | None = Field(default=None, max_length=255)
    is_excluded: bool | None = None
    fund_center_code: str | None = Field(default=None, min_length=1, max_length=20)
    cost_center_code: str | None = Field(default=None, min_length=1, max_length=20)


class ExpenseItemOut(BaseModel):
    id: int
    card_transaction_id: int | None
    expense_category_code: str
    amount_krw: Decimal
    memo: str | None
    is_excluded: bool
    #: null이면 "리포트 값 상속". 화면의 "부서 지정" 컬럼이 이 두 필드를 본다.
    fund_center_code: str | None
    cost_center_code: str | None
    #: coalesce 결과. Agent가 상속 규칙을 다시 구현하지 않아도 되게 함께 내려준다.
    effective_fund_center_code: str | None
    effective_cost_center_code: str | None
    merchant_name: str | None
    approved_at: datetime | None


class ExpenseReportListItem(BaseModel):
    id: int
    report_no: str
    status: ExpenseReportStatus
    trip_id: int
    trip_no: str
    trip_title: str
    trip_start_date: date
    trip_end_date: date
    user_id: int
    user_name: str
    approver_id: int | None
    approver_name: str | None
    fund_center_code: str | None
    cost_center_code: str | None
    total_amount_krw: Decimal
    submitted_at: datetime | None
    approved_at: datetime | None


class ExpenseReportDetail(ExpenseReportListItem):
    reject_reason: str | None
    created_at: datetime
    updated_at: datetime
    items: list[ExpenseItemOut]


class MatchCandidateOut(BaseModel):
    transaction_id: int
    approved_at: datetime
    merchant_name: str
    merchant_category_code: str
    amount_krw: Decimal
    suggested_category_code: str
    reasons: list[str]
    #: 이미 이 리포트의 항목으로 담긴 거래. 화면이 "담기" 버튼을 비활성화한다.
    already_added: bool
```

- [ ] **Step 3: 임포트가 되는지 확인한다**

Run: `cd backend && uv run python -c "from app.schemas.expense import ExpenseReportDetail; from app.schemas.card import CardOut; print('ok')"`
Expected: `ok`

(`python3`를 맨몸으로 부르면 pyenv 때문에 죽는다. 반드시 `uv run`.)

- [ ] **Step 4: 커밋**

```bash
git add backend/app/schemas/card.py backend/app/schemas/expense.py
git commit -m "feat: add card and expense schemas"
```

---

## Task 8: 테스트 팩토리 확장

**Files:**
- Modify: `backend/tests/factories.py`
- Test: `backend/tests/test_factories.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_factories.py`에 추가:

```python
from datetime import datetime, timezone
from decimal import Decimal

from app.enums import ExpenseReportStatus
from tests.factories import (
    make_card,
    make_card_transaction,
    make_expense_item,
    make_expense_report,
)


async def test_make_card_and_transaction(db_session):
    user = await make_user(db_session)
    card = await make_card(db_session, user=user)
    transaction = await make_card_transaction(
        db_session, card=card, approved_at=datetime(2026, 5, 11, 3, tzinfo=timezone.utc)
    )
    assert transaction.card_id == card.id
    assert transaction.amount_krw == Decimal("30000")
    assert transaction.is_cancelled is False


async def test_make_expense_report_and_item(db_session):
    manager = await make_user(db_session, role=UserRole.MANAGER)
    owner = await make_user(db_session, manager=manager)
    trip = await make_trip(db_session, user=owner, status=TripStatus.COMPLETED)
    report = await make_expense_report(db_session, trip=trip, approver=manager)
    item = await make_expense_item(db_session, report=report, amount=Decimal("12000"))
    assert report.status is ExpenseReportStatus.DRAFT
    assert report.trip_id == trip.id
    assert report.user_id == owner.id
    assert item.report_id == report.id
```

`test_factories.py` 상단에 이미 있는 import(`make_user`·`make_trip`·`UserRole`·`TripStatus`)를 확인하고 없으면 추가한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_factories.py -v`
Expected: FAIL — `ImportError: cannot import name 'make_card'`

- [ ] **Step 3: 구현한다**

`backend/tests/factories.py`에 추가한다 (파일 상단 import에 `datetime`·`timezone`과 모델 4종을 더한다):

```python
async def make_card(
    session: AsyncSession, *, user: User, is_active: bool = True
) -> CorporateCard:
    n = _next()
    card = CorporateCard(
        user_id=user.id,
        card_no_masked=f"5678-****-****-9{n:03d}",
        brand="BC",
        is_active=is_active,
    )
    session.add(card)
    await session.flush()
    return card


async def make_card_transaction(
    session: AsyncSession,
    *,
    card: CorporateCard,
    approved_at: datetime,
    merchant_category_code: str = "MEAL",
    amount: Decimal = Decimal("30000"),
    is_cancelled: bool = False,
) -> CardTransaction:
    transaction = CardTransaction(
        card_id=card.id,
        approved_at=approved_at,
        merchant_name="한밭식당",
        merchant_category_code=merchant_category_code,
        amount=amount,
        currency_code="KRW",
        amount_krw=amount,
        is_cancelled=is_cancelled,
    )
    session.add(transaction)
    await session.flush()
    return transaction


async def make_expense_report(
    session: AsyncSession,
    *,
    trip: Trip,
    approver: User | None = None,
    status: ExpenseReportStatus = ExpenseReportStatus.DRAFT,
    fund_center_code: str | None = "FC1010",
    cost_center_code: str | None = None,
) -> ExpenseReport:
    """report_no는 EX-9999-* 를 쓴다 — 채번 테스트(현재 연도)와 겹치지 않게 하기 위해서다."""
    n = _next()
    report = ExpenseReport(
        report_no=f"EX-9999-{n:04d}",
        trip_id=trip.id,
        user_id=trip.user_id,
        status=status,
        fund_center_code=fund_center_code,
        cost_center_code=cost_center_code or trip.cost_center_code,
        approver_id=approver.id if approver else trip.approver_id,
    )
    session.add(report)
    await session.flush()
    return report


async def make_expense_item(
    session: AsyncSession,
    *,
    report: ExpenseReport,
    amount: Decimal = Decimal("30000"),
    card_transaction: CardTransaction | None = None,
    expense_category_code: str = "MEAL",
    is_excluded: bool = False,
    fund_center_code: str | None = None,
    cost_center_code: str | None = None,
) -> ExpenseItem:
    item = ExpenseItem(
        report_id=report.id,
        card_transaction_id=card_transaction.id if card_transaction else None,
        expense_category_code=expense_category_code,
        amount_krw=amount,
        is_excluded=is_excluded,
        fund_center_code=fund_center_code,
        cost_center_code=cost_center_code,
    )
    session.add(item)
    await session.flush()
    return item
```

`make_trip_master_data`에 정산 비목을 더한다 — 정산 쓰기 경로가 `EXPENSE_CATEGORY`를 검증하기 때문이다. `groups` 딕셔너리에 다음 두 줄을 추가한다:

```python
        "EXPENSE_CATEGORY": ["MEAL", "TRANSPORT", "LODGING", "ETC"],
        "MERCHANT_CATEGORY": ["MEAL", "TRANSPORT", "LODGING", "ETC"],
```

그리고 코스트센터만 만들던 마지막 블록 아래에 펀드센터도 같은 방식(있으면 건너뜀)으로 만든다:

```python
    fund_center_code = "FC1010"
    existing_fund = (
        await session.execute(
            select(FundCenter.code).where(FundCenter.code == fund_center_code)
        )
    ).scalar_one_or_none()
    if existing_fund is None:
        await make_fund_center(session, fund_center_code)
```

`seeded` 세션에서 불러도 `UniqueViolation`이 나지 않아야 한다 (Phase 2 결함 #7). 시드도 `FC1010`·`CC2030`을 만들므로 존재 확인이 반드시 있어야 한다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_factories.py -v`
Expected: PASS

- [ ] **Step 5: `seeded` 세션에서도 안전한지 확인한다**

`backend/tests/test_factories.py`에 추가:

```python
async def test_make_trip_master_data_is_safe_on_a_seeded_session(seeded):
    """seed와 코드·센터가 겹치므로 두 번 만들면 UniqueViolation이 savepoint 안에서
    터지고, 이후 모든 문장이 PendingRollbackError가 되어 원인이 묻힌다."""
    await make_trip_master_data(seeded)
    await make_trip_master_data(seeded)
```

Run: `cd backend && uv run pytest tests/test_factories.py -v`
Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add backend/tests/factories.py backend/tests/test_factories.py
git commit -m "test: add card and expense factories"
```

---

## Task 9: 카드 조회 서비스 + 라우터

**Files:**
- Create: `backend/app/services/cards.py`, `backend/app/routers/cards.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_cards_api.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_cards_api.py`:

```python
"""카드 조회 API. 남의 카드·거래는 보이지 않아야 한다."""

from datetime import datetime, timezone
from decimal import Decimal

from app.enums import UserRole
from tests.factories import make_card, make_card_transaction, make_user


async def test_lists_only_my_cards(client, db_session, login_as, seeded):
    headers = await login_as("user1@skon.example")
    response = await client.get("/api/v1/cards", headers=headers)
    assert response.status_code == 200
    cards = response.json()
    assert len(cards) >= 1
    assert all("card_no_masked" in card for card in cards)


async def test_card_transactions_are_scoped_to_my_cards(client, db_session, login_as, seeded):
    """다른 사용자의 카드 id를 직접 넘겨도 남의 거래가 새지 않는다."""
    other = await make_user(db_session, name="남의사람")
    other_card = await make_card(db_session, user=other)
    await make_card_transaction(
        db_session, card=other_card, approved_at=datetime(2026, 5, 11, 3, tzinfo=timezone.utc)
    )
    await db_session.flush()

    headers = await login_as("user1@skon.example")
    response = await client.get(
        f"/api/v1/card-transactions?card_id={other_card.id}", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_card_transactions_filter_by_date_range(client, login_as, seeded):
    headers = await login_as("user1@skon.example")
    response = await client.get(
        "/api/v1/card-transactions?approved_from=2026-01-01&approved_to=2026-12-31&size=5",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["size"] == 5
    assert len(body["items"]) <= 5


async def test_cancelled_transactions_are_hidden_by_default(client, db_session, login_as, seeded):
    user = await make_user(db_session, name="취소테스트")
    card = await make_card(db_session, user=user)
    await make_card_transaction(
        db_session,
        card=card,
        approved_at=datetime(2026, 5, 11, 3, tzinfo=timezone.utc),
        is_cancelled=True,
        amount=Decimal("77000"),
    )
    await db_session.commit()

    # 이 사용자로 로그인할 수 없으므로(비밀번호 해시가 'x') 서비스 함수를 직접 부른다.
    from app.services.cards import CardTxnFilters, list_card_transactions

    visible = await list_card_transactions(db_session, user=user, filters=CardTxnFilters())
    assert visible.total == 0

    with_cancelled = await list_card_transactions(
        db_session, user=user, filters=CardTxnFilters(include_cancelled=True)
    )
    assert with_cancelled.total == 1


async def test_cards_require_authentication(client):
    response = await client.get("/api/v1/cards")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_CREDENTIALS"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_cards_api.py -v`
Expected: FAIL — 404 (라우터 없음)

- [ ] **Step 3: 서비스를 구현한다**

`backend/app/services/cards.py`:

```python
"""법인카드·카드거래 조회.

카드 소유자 필터는 **서비스가** 건다. 라우터가 card_id를 그대로 where에 넣으면 남의
카드 id를 넣었을 때 남의 거래가 새어나간다 — 이 프로젝트는 타인 리소스를 404/0건으로
다룬다.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CardTransaction, CorporateCard, User
from app.schemas.card import CardOut, CardTransactionOut
from app.schemas.common import Page
from app.services.matching import KST


def _start_of(day: date, *, plus_one: bool = False) -> datetime:
    """날짜 필터는 KST 자정 경계로 자른다. approved_at이 timestamptz이므로 date를 그대로
    비교하면 UTC 경계가 되어 화면에 보이는 날짜와 어긋난다."""
    target = day + timedelta(days=1) if plus_one else day
    return datetime.combine(target, time.min, tzinfo=KST)


@dataclass(frozen=True)
class CardTxnFilters:
    card_id: int | None = None
    approved_from: date | None = None
    approved_to: date | None = None
    merchant_category_code: str | None = None
    q: str | None = None
    include_cancelled: bool = False
    page: int = 1
    size: int = 20


async def load_my_card_ids(session: AsyncSession, user: User) -> list[int]:
    rows = await session.execute(
        select(CorporateCard.id).where(CorporateCard.user_id == user.id)
    )
    return list(rows.scalars().all())


async def list_my_cards(session: AsyncSession, *, user: User) -> list[CardOut]:
    rows = (
        (
            await session.execute(
                select(CorporateCard)
                .where(CorporateCard.user_id == user.id)
                .order_by(CorporateCard.id)
            )
        )
        .scalars()
        .all()
    )
    return [CardOut.model_validate(row) for row in rows]


async def list_card_transactions(
    session: AsyncSession, *, user: User, filters: CardTxnFilters
) -> Page[CardTransactionOut]:
    card_ids = await load_my_card_ids(session, user)
    if filters.card_id is not None:
        # 교집합을 취한다. 남의 card_id면 빈 목록이 되고 존재 여부도 알려주지 않는다.
        card_ids = [card_id for card_id in card_ids if card_id == filters.card_id]
    if not card_ids:
        return Page[CardTransactionOut](items=[], total=0, page=filters.page, size=filters.size)

    conditions: list[ColumnElement[bool]] = [CardTransaction.card_id.in_(card_ids)]
    if not filters.include_cancelled:
        conditions.append(CardTransaction.is_cancelled.is_(False))
    if filters.approved_from:
        conditions.append(CardTransaction.approved_at >= _start_of(filters.approved_from))
    if filters.approved_to:
        conditions.append(CardTransaction.approved_at < _start_of(filters.approved_to, plus_one=True))
    if filters.merchant_category_code:
        conditions.append(
            CardTransaction.merchant_category_code == filters.merchant_category_code
        )
    if filters.q:
        conditions.append(CardTransaction.merchant_name.ilike(f"%{filters.q}%"))

    total = (
        await session.execute(
            select(func.count()).select_from(CardTransaction).where(*conditions)
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(CardTransaction)
                .where(*conditions)
                .order_by(CardTransaction.approved_at.desc(), CardTransaction.id.desc())
                .offset((filters.page - 1) * filters.size)
                .limit(filters.size)
            )
        )
        .scalars()
        .all()
    )
    return Page[CardTransactionOut](
        items=[CardTransactionOut.model_validate(row) for row in rows],
        total=total,
        page=filters.page,
        size=filters.size,
    )
```

- [ ] **Step 4: 라우터를 구현하고 등록한다**

`backend/app/routers/cards.py`:

```python
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser, DbSession
from app.schemas.card import CardOut, CardTransactionOut
from app.schemas.common import Page
from app.services import cards as card_service

router = APIRouter(prefix="/api/v1", tags=["cards"])


@router.get("/cards", response_model=list[CardOut])
async def list_cards(user: CurrentUser, session: DbSession) -> list[CardOut]:
    return await card_service.list_my_cards(session, user=user)


@router.get("/card-transactions", response_model=Page[CardTransactionOut])
async def list_card_transactions(
    user: CurrentUser,
    session: DbSession,
    card_id: int | None = None,
    approved_from: date | None = None,
    approved_to: date | None = None,
    merchant_category_code: str | None = None,
    q: str | None = None,
    include_cancelled: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[CardTransactionOut]:
    return await card_service.list_card_transactions(
        session,
        user=user,
        filters=card_service.CardTxnFilters(
            card_id=card_id,
            approved_from=approved_from,
            approved_to=approved_to,
            merchant_category_code=merchant_category_code,
            q=q,
            include_cancelled=include_cancelled,
            page=page,
            size=size,
        ),
    )
```

`backend/app/main.py`: import 줄을 `from app.routers import auth, cards, centers, codes, notifications, trips`로 바꾸고 `app.include_router(cards.router)`를 `auth` 다음 줄에 추가한다.

- [ ] **Step 5: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_cards_api.py -v`
Expected: PASS (5건)

- [ ] **Step 6: mutation으로 소유자 필터를 확인한다**

`list_card_transactions`의 `card_ids = [card_id for card_id in card_ids if card_id == filters.card_id]`를 `card_ids = [filters.card_id]`로 바꾸고:

Run: `cd backend && uv run pytest tests/test_cards_api.py -q`
Expected: FAIL — `test_card_transactions_are_scoped_to_my_cards`. 되돌린다.

- [ ] **Step 7: 커밋**

```bash
git add backend/app/services/cards.py backend/app/routers/cards.py backend/app/main.py backend/tests/test_cards_api.py
git commit -m "feat: add card and card transaction endpoints"
```

---

## Task 10: 정산서 조회·생성·수정 서비스

**Files:**
- Create: `backend/app/services/expenses.py`
- Modify: `backend/app/services/trips.py` (`_names_by_id` → `load_user_names` 공개)
- Test: `backend/tests/test_expenses_service_write.py`

- [ ] **Step 1: `_names_by_id`를 공개 이름으로 바꾼다**

`backend/app/services/trips.py`에서 `async def _names_by_id(` → `async def load_user_names(`로 바꾸고, 같은 파일의 호출 2곳(`build_list_items`, `list_timeline`)을 함께 고친다. 정산 서비스가 같은 조회를 다시 구현하면 N+1 방지 규칙이 두 벌이 된다.

Run: `cd backend && grep -n "_names_by_id\|load_user_names" app/services/trips.py`
Expected: `load_user_names` 3곳, `_names_by_id` 0곳

Run: `cd backend && uv run pytest tests/test_trips_service_read.py -q`
Expected: PASS

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`backend/tests/test_expenses_service_write.py`:

```python
"""정산서 생성·수정 서비스."""

import pytest

from app.enums import ExpenseReportStatus, TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.schemas.expense import ExpenseReportCreate, ExpenseReportUpdate
from app.services.expenses import create_report, get_report, list_reports, update_report
from app.services.expenses import ExpenseFilters
from tests.factories import (
    make_expense_report,
    make_trip,
    make_trip_master_data,
    make_user,
)


async def _org(session):
    await make_trip_master_data(session)
    manager = await make_user(session, role=UserRole.MANAGER, name="김결재")
    owner = await make_user(session, manager=manager, name="박신청")
    return manager, owner


async def test_create_report_inherits_cost_center_and_approver(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )

    detail = await create_report(
        db_session, user=owner, payload=ExpenseReportCreate(trip_id=trip.id)
    )

    assert detail.status is ExpenseReportStatus.DRAFT
    assert detail.cost_center_code == trip.cost_center_code
    assert detail.fund_center_code is None
    assert detail.approver_id == manager.id
    assert detail.trip_no == trip.trip_no
    assert detail.report_no.startswith("EX-")
    assert detail.items == []


async def test_create_report_is_rejected_for_a_draft_trip(db_session):
    _, owner = await _org(db_session)
    trip = await make_trip(db_session, user=owner, status=TripStatus.DRAFT)
    with pytest.raises(ConflictError) as excinfo:
        await create_report(db_session, user=owner, payload=ExpenseReportCreate(trip_id=trip.id))
    assert excinfo.value.code == "TRIP_NOT_REPORTABLE"


async def test_only_one_report_per_trip(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    await create_report(db_session, user=owner, payload=ExpenseReportCreate(trip_id=trip.id))
    with pytest.raises(ConflictError) as excinfo:
        await create_report(db_session, user=owner, payload=ExpenseReportCreate(trip_id=trip.id))
    assert excinfo.value.code == "EXPENSE_ALREADY_EXISTS"


async def test_approver_cannot_create_the_report(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    with pytest.raises(ForbiddenError) as excinfo:
        await create_report(db_session, user=manager, payload=ExpenseReportCreate(trip_id=trip.id))
    assert excinfo.value.code == "NOT_TRIP_OWNER"


async def test_creating_a_report_for_someone_elses_trip_is_a_404(db_session):
    _, owner = await _org(db_session)
    stranger = await make_user(db_session, name="남의사람")
    trip = await make_trip(db_session, user=owner, status=TripStatus.COMPLETED)
    with pytest.raises(NotFoundError) as excinfo:
        await create_report(
            db_session, user=stranger, payload=ExpenseReportCreate(trip_id=trip.id)
        )
    assert excinfo.value.code == "TRIP_NOT_FOUND"


async def test_update_sets_the_header_centers(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(db_session, trip=trip, approver=manager)

    detail = await update_report(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseReportUpdate(fund_center_code="FC1010", cost_center_code="CC2030"),
    )
    assert detail.fund_center_code == "FC1010"
    assert detail.cost_center_code == "CC2030"


async def test_update_rejects_an_unknown_fund_center(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(db_session, trip=trip, approver=manager)
    with pytest.raises(ValidationError) as excinfo:
        await update_report(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseReportUpdate(fund_center_code="FC9999"),
        )
    assert excinfo.value.code == "INVALID_FUND_CENTER"
    assert excinfo.value.field == "fund_center_code"


async def test_update_is_rejected_once_submitted(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(
        db_session, trip=trip, approver=manager, status=ExpenseReportStatus.SUBMITTED
    )
    with pytest.raises(ConflictError) as excinfo:
        await update_report(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseReportUpdate(fund_center_code="FC1010"),
        )
    assert excinfo.value.code == "EXPENSE_NOT_EDITABLE"


async def test_get_report_hides_other_peoples_reports(db_session):
    manager, owner = await _org(db_session)
    stranger = await make_user(db_session, name="남의사람")
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(db_session, trip=trip, approver=manager)
    with pytest.raises(NotFoundError) as excinfo:
        await get_report(db_session, user=stranger, report_id=report.id)
    assert excinfo.value.code == "EXPENSE_NOT_FOUND"

    # 결재자는 볼 수 있다.
    assert (await get_report(db_session, user=manager, report_id=report.id)).id == report.id


async def test_list_scopes(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    await make_expense_report(
        db_session, trip=trip, approver=manager, status=ExpenseReportStatus.SUBMITTED
    )

    mine = await list_reports(db_session, user=owner, filters=ExpenseFilters(scope="mine"))
    assert mine.total == 1

    inbox = await list_reports(db_session, user=manager, filters=ExpenseFilters(scope="approvals"))
    assert inbox.total == 1

    with pytest.raises(ForbiddenError) as excinfo:
        await list_reports(db_session, user=owner, filters=ExpenseFilters(scope="all"))
    assert excinfo.value.code == "FORBIDDEN_SCOPE"


async def test_list_query_count_is_fixed_regardless_of_row_count(db_session):
    """목록에서 행마다 헬퍼를 부르면 N+1이 된다. 출장 목록과 같은 규칙을 정산에도 건다."""
    manager, owner = await _org(db_session)
    for _ in range(3):
        trip = await make_trip(
            db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
        )
        await make_expense_report(db_session, trip=trip, approver=manager)

    from sqlalchemy import event

    statements: list[str] = []
    connection = await db_session.connection()

    def before_execute(*args, **kwargs):
        statements.append("q")

    event.listen(connection.sync_connection.engine, "before_cursor_execute", before_execute)
    try:
        result = await list_reports(db_session, user=owner, filters=ExpenseFilters())
    finally:
        event.remove(connection.sync_connection.engine, "before_cursor_execute", before_execute)

    assert result.total == 3
    # count + rows + trips + names = 4
    assert len(statements) == 4
```

- [ ] **Step 3: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_expenses_service_write.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.expenses'`

- [ ] **Step 4: 서비스의 조회·생성·수정 부분을 구현한다**

`backend/app/services/expenses.py`:

```python
"""정산 서비스. 라우터는 이 모듈의 함수만 부르고 스키마를 그대로 응답한다.

`relationship()`을 붙이지 않는다 — 출장 제목·사용자 이름은 id를 모아 한 번에 조회한다.
목록에서 행마다 헬퍼를 부르면 N+1이 되고, 그걸 막는 쿼리 수 고정 테스트가 붙어 있다.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ActivityAction,
    EntityType,
    ExpenseReportStatus,
    UserRole,
)
from app.errors import ConflictError, ForbiddenError, NotFoundError
from app.models import CardTransaction, ExpenseItem, ExpenseReport, Trip, User
from app.schemas.common import Page
from app.schemas.expense import (
    ExpenseItemOut,
    ExpenseReportCreate,
    ExpenseReportDetail,
    ExpenseReportListItem,
    ExpenseReportUpdate,
)
from app.services.centers import assert_cost_center, assert_fund_center
from app.services.expense_rules import (
    assert_report_creatable,
    assert_report_editable,
    assert_report_owner,
    can_view_report,
    effective_center,
)
from app.services.history import record_transition
from app.services.numbering import next_report_no
from app.services.trip_rules import assert_trip_owner
from app.services.trips import load_user_names, load_visible_trip


@dataclass(frozen=True)
class ExpenseFilters:
    scope: str = "mine"
    status: list[ExpenseReportStatus] = field(default_factory=list)
    q: str | None = None
    page: int = 1
    size: int = 20


async def build_list_items(
    session: AsyncSession, reports: list[ExpenseReport]
) -> list[ExpenseReportListItem]:
    if not reports:
        return []
    trip_rows = (
        await session.execute(
            select(
                Trip.id, Trip.trip_no, Trip.title, Trip.start_date, Trip.end_date
            ).where(Trip.id.in_({report.trip_id for report in reports}))
        )
    ).all()
    trips = {row[0]: row for row in trip_rows}
    names = await load_user_names(
        session,
        {report.user_id for report in reports}
        | {report.approver_id for report in reports if report.approver_id is not None},
    )
    items = []
    for report in reports:
        trip = trips[report.trip_id]
        items.append(
            ExpenseReportListItem(
                id=report.id,
                report_no=report.report_no,
                status=report.status,
                trip_id=report.trip_id,
                trip_no=trip[1],
                trip_title=trip[2],
                trip_start_date=trip[3],
                trip_end_date=trip[4],
                user_id=report.user_id,
                user_name=names.get(report.user_id, ""),
                approver_id=report.approver_id,
                approver_name=names.get(report.approver_id) if report.approver_id else None,
                fund_center_code=report.fund_center_code,
                cost_center_code=report.cost_center_code,
                total_amount_krw=report.total_amount_krw,
                submitted_at=report.submitted_at,
                approved_at=report.approved_at,
            )
        )
    return items


async def _load_items(session: AsyncSession, report: ExpenseReport) -> list[ExpenseItemOut]:
    rows = (
        (
            await session.execute(
                select(ExpenseItem)
                .where(ExpenseItem.report_id == report.id)
                .order_by(ExpenseItem.id)
            )
        )
        .scalars()
        .all()
    )
    transaction_ids = {row.card_transaction_id for row in rows if row.card_transaction_id}
    transactions = {}
    if transaction_ids:
        transaction_rows = (
            await session.execute(
                select(
                    CardTransaction.id, CardTransaction.merchant_name, CardTransaction.approved_at
                ).where(CardTransaction.id.in_(transaction_ids))
            )
        ).all()
        transactions = {row[0]: row for row in transaction_rows}
    return [
        ExpenseItemOut(
            id=row.id,
            card_transaction_id=row.card_transaction_id,
            expense_category_code=row.expense_category_code,
            amount_krw=row.amount_krw,
            memo=row.memo,
            is_excluded=row.is_excluded,
            fund_center_code=row.fund_center_code,
            cost_center_code=row.cost_center_code,
            effective_fund_center_code=effective_center(
                row.fund_center_code, report.fund_center_code
            ),
            effective_cost_center_code=effective_center(
                row.cost_center_code, report.cost_center_code
            ),
            merchant_name=(
                transactions[row.card_transaction_id][1]
                if row.card_transaction_id in transactions
                else None
            ),
            approved_at=(
                transactions[row.card_transaction_id][2]
                if row.card_transaction_id in transactions
                else None
            ),
        )
        for row in rows
    ]


async def build_detail(session: AsyncSession, report: ExpenseReport) -> ExpenseReportDetail:
    [item] = await build_list_items(session, [report])
    return ExpenseReportDetail(
        **item.model_dump(),
        reject_reason=report.reject_reason,
        created_at=report.created_at,
        updated_at=report.updated_at,
        items=await _load_items(session, report),
    )


async def load_visible_report(
    session: AsyncSession, report_id: int, user: User
) -> ExpenseReport:
    """볼 수 없는 정산서는 없는 것으로 취급한다 (spec 7: 타인 리소스 접근도 404)."""
    report = await session.get(ExpenseReport, report_id)
    if report is None or not can_view_report(
        user_id=user.id,
        role=user.role,
        owner_id=report.user_id,
        approver_id=report.approver_id,
    ):
        raise NotFoundError("EXPENSE_NOT_FOUND", "정산서를 찾을 수 없습니다")
    return report


def _scope_conditions(user: User, scope: str) -> list[ColumnElement[bool]]:
    if scope == "mine":
        return [ExpenseReport.user_id == user.id]
    if scope == "approvals":
        return [ExpenseReport.approver_id == user.id]
    if user.role is not UserRole.ADMIN:
        raise ForbiddenError("FORBIDDEN_SCOPE", "전체 정산서를 조회할 권한이 없습니다")
    return []


async def list_reports(
    session: AsyncSession, *, user: User, filters: ExpenseFilters
) -> Page[ExpenseReportListItem]:
    conditions = _scope_conditions(user, filters.scope)
    if filters.status:
        conditions.append(ExpenseReport.status.in_(filters.status))
    if filters.q:
        like = f"%{filters.q}%"
        conditions.append(
            or_(
                ExpenseReport.report_no.ilike(like),
                Trip.title.ilike(like),
                Trip.trip_no.ilike(like),
            )
        )

    joined = select(ExpenseReport).join(Trip, Trip.id == ExpenseReport.trip_id)
    total = (
        await session.execute(
            select(func.count())
            .select_from(ExpenseReport)
            .join(Trip, Trip.id == ExpenseReport.trip_id)
            .where(*conditions)
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                joined.where(*conditions)
                .order_by(ExpenseReport.id.desc())
                .offset((filters.page - 1) * filters.size)
                .limit(filters.size)
            )
        )
        .scalars()
        .all()
    )
    return Page[ExpenseReportListItem](
        items=await build_list_items(session, list(rows)),
        total=total,
        page=filters.page,
        size=filters.size,
    )


async def get_report(
    session: AsyncSession, *, user: User, report_id: int
) -> ExpenseReportDetail:
    return await build_detail(session, await load_visible_report(session, report_id, user))


async def create_report(
    session: AsyncSession, *, user: User, payload: ExpenseReportCreate
) -> ExpenseReportDetail:
    trip = await load_visible_trip(session, payload.trip_id, user)
    assert_trip_owner(user_id=user.id, owner_id=trip.user_id)
    assert_report_creatable(trip.status)

    existing = (
        await session.execute(
            select(ExpenseReport.id).where(ExpenseReport.trip_id == trip.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        # trip_id에 unique 제약이 있으므로 이 검사가 없으면 flush에서 IntegrityError가
        # 나고 catch-all 핸들러에 걸려 500이 된다. Agent는 5xx를 재시도한다.
        raise ConflictError("EXPENSE_ALREADY_EXISTS", "이 출장의 정산서가 이미 있습니다")

    report = ExpenseReport(
        report_no=await next_report_no(session, datetime.now(timezone.utc).date()),
        trip_id=trip.id,
        user_id=trip.user_id,
        status=ExpenseReportStatus.DRAFT,
        # cost_center_code는 출장에서 승계된다 (spec 5.5). fund_center_code는 출장에
        # 없으므로 비워 두고, 제출 전에 사용자가 고른다.
        cost_center_code=trip.cost_center_code,
        fund_center_code=None,
        approver_id=trip.approver_id,
        total_amount_krw=Decimal("0"),
    )
    session.add(report)
    await session.flush()
    await record_transition(
        session,
        entity_type=EntityType.EXPENSE_REPORT,
        entity_id=report.id,
        actor_id=user.id,
        action=ActivityAction.CREATED,
        to_status=ExpenseReportStatus.DRAFT.value,
        memo=f"{trip.trip_no} 정산서 작성",
    )
    await session.commit()
    return await build_detail(session, report)


async def update_report(
    session: AsyncSession, *, user: User, report_id: int, payload: ExpenseReportUpdate
) -> ExpenseReportDetail:
    report = await load_visible_report(session, report_id, user)
    assert_report_owner(user_id=user.id, owner_id=report.user_id)
    assert_report_editable(report.status)

    changes = payload.model_dump(exclude_unset=True)
    if "fund_center_code" in changes and changes["fund_center_code"] is not None:
        await assert_fund_center(session, changes["fund_center_code"])
    if "cost_center_code" in changes and changes["cost_center_code"] is not None:
        await assert_cost_center(session, changes["cost_center_code"])

    for name, value in changes.items():
        setattr(report, name, value)
    await session.flush()
    await record_transition(
        session,
        entity_type=EntityType.EXPENSE_REPORT,
        entity_id=report.id,
        actor_id=user.id,
        action=ActivityAction.UPDATED,
        from_status=report.status.value,
        to_status=report.status.value,
        memo="정산서 헤더 수정",
    )
    await session.commit()
    return await build_detail(session, report)
```

- [ ] **Step 5: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_expenses_service_write.py -v`
Expected: PASS (11건)

- [ ] **Step 6: mutation 2건**

| mutation | 기대 |
|---|---|
| `assert_report_creatable(trip.status)` 줄 삭제 | `test_create_report_is_rejected_for_a_draft_trip` FAIL |
| `assert_trip_owner(...)` 줄 삭제 | `test_approver_cannot_create_the_report` FAIL |

각각 확인 후 되돌린다.

- [ ] **Step 7: 커밋**

```bash
git add backend/app/services/expenses.py backend/app/services/trips.py backend/tests/test_expenses_service_write.py
git commit -m "feat: add expense report read, create and header update services"
```

---

## Task 11: 정산 항목 CRUD + 합계 재계산

**Files:**
- Modify: `backend/app/services/expenses.py`
- Test: `backend/tests/test_expenses_service_write.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_expenses_service_write.py`에 추가:

```python
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.schemas.expense import ExpenseItemCreate, ExpenseItemUpdate
from app.services.expense_rules import MAX_ITEM_AMOUNT
from app.services.expenses import add_item, delete_item, update_item
from tests.factories import make_card, make_card_transaction


async def _report_with_card(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(db_session, trip=trip, approver=manager)
    card = await make_card(db_session, user=owner)
    return manager, owner, trip, report, card


async def test_add_item_from_a_card_transaction_uses_its_amount(db_session):
    _, owner, trip, report, card = await _report_with_card(db_session)
    transaction = await make_card_transaction(
        db_session,
        card=card,
        approved_at=datetime.combine(trip.start_date, datetime.min.time(), tzinfo=timezone.utc)
        + timedelta(hours=3),
        amount=Decimal("45000"),
    )

    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(
            card_transaction_id=transaction.id, expense_category_code="MEAL"
        ),
    )

    assert len(detail.items) == 1
    assert detail.items[0].amount_krw == Decimal("45000")
    assert detail.items[0].merchant_name == "한밭식당"
    assert detail.total_amount_krw == Decimal("45000")


async def test_manual_item_requires_an_amount(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    with pytest.raises(ValidationError) as excinfo:
        await add_item(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseItemCreate(expense_category_code="MEAL"),
        )
    assert excinfo.value.code == "AMOUNT_REQUIRED"
    assert excinfo.value.field == "amount_krw"


async def test_add_item_rejects_an_unknown_category(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    with pytest.raises(ValidationError) as excinfo:
        await add_item(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseItemCreate(
                expense_category_code="NOPE", amount_krw=Decimal("1000")
            ),
        )
    assert excinfo.value.code == "INVALID_CODE"
    assert excinfo.value.field == "expense_category_code"


async def test_add_item_rejects_someone_elses_transaction(db_session):
    _, owner, trip, report, _ = await _report_with_card(db_session)
    stranger = await make_user(db_session, name="남의사람")
    stranger_card = await make_card(db_session, user=stranger)
    transaction = await make_card_transaction(
        db_session,
        card=stranger_card,
        approved_at=datetime.combine(trip.start_date, datetime.min.time(), tzinfo=timezone.utc),
    )
    with pytest.raises(ValidationError) as excinfo:
        await add_item(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseItemCreate(
                card_transaction_id=transaction.id, expense_category_code="MEAL"
            ),
        )
    assert excinfo.value.code == "INVALID_TRANSACTION"
    assert excinfo.value.field == "card_transaction_id"


async def test_the_same_transaction_cannot_be_added_twice(db_session):
    _, owner, trip, report, card = await _report_with_card(db_session)
    transaction = await make_card_transaction(
        db_session,
        card=card,
        approved_at=datetime.combine(trip.start_date, datetime.min.time(), tzinfo=timezone.utc),
    )
    payload = ExpenseItemCreate(card_transaction_id=transaction.id, expense_category_code="MEAL")
    await add_item(db_session, user=owner, report_id=report.id, payload=payload)
    with pytest.raises(ConflictError) as excinfo:
        await add_item(db_session, user=owner, report_id=report.id, payload=payload)
    assert excinfo.value.code == "EXPENSE_ITEM_DUPLICATE"


async def test_item_amount_above_the_column_limit_is_a_400_not_a_500(db_session):
    """Numeric(14,2) 오버플로가 flush에서 터지면 500이 되고 Agent가 무한 재시도한다."""
    _, owner, _, report, _ = await _report_with_card(db_session)
    with pytest.raises(ValidationError) as excinfo:
        await add_item(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseItemCreate(
                expense_category_code="MEAL", amount_krw=MAX_ITEM_AMOUNT + Decimal("1")
            ),
        )
    assert excinfo.value.code == "INVALID_AMOUNT"


async def test_excluded_items_drop_out_of_the_total(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("10000")),
    )
    item_id = detail.items[0].id
    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("5000")),
    )
    assert detail.total_amount_krw == Decimal("15000")

    detail = await update_item(
        db_session, user=owner, item_id=item_id, payload=ExpenseItemUpdate(is_excluded=True)
    )
    assert detail.total_amount_krw == Decimal("5000")


async def test_item_center_override_shows_up_as_effective_value(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    await update_report(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseReportUpdate(fund_center_code="FC1010", cost_center_code="CC2030"),
    )
    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("1000")),
    )
    item = detail.items[0]
    assert item.cost_center_code is None
    assert item.effective_cost_center_code == "CC2030"

    detail = await update_item(
        db_session,
        user=owner,
        item_id=item.id,
        payload=ExpenseItemUpdate(cost_center_code="CC2040"),
    )
    assert detail.items[0].cost_center_code == "CC2040"
    assert detail.items[0].effective_cost_center_code == "CC2040"


async def test_delete_item_recomputes_the_total(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("7000")),
    )
    detail = await delete_item(db_session, user=owner, item_id=detail.items[0].id)
    assert detail.items == []
    assert detail.total_amount_krw == Decimal("0")


async def test_items_cannot_be_touched_once_submitted(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(
        db_session, trip=trip, approver=manager, status=ExpenseReportStatus.SUBMITTED
    )
    with pytest.raises(ConflictError) as excinfo:
        await add_item(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("1000")),
        )
    assert excinfo.value.code == "EXPENSE_NOT_EDITABLE"


async def test_updating_someone_elses_item_is_a_404(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    stranger = await make_user(db_session, name="남의사람")
    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("1000")),
    )
    with pytest.raises(NotFoundError) as excinfo:
        await update_item(
            db_session,
            user=stranger,
            item_id=detail.items[0].id,
            payload=ExpenseItemUpdate(memo="여기 손대지 마"),
        )
    assert excinfo.value.code == "EXPENSE_NOT_FOUND"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_expenses_service_write.py -v`
Expected: FAIL — `ImportError: cannot import name 'add_item'`

- [ ] **Step 3: 구현한다**

`backend/app/services/expenses.py`에 추가한다. import에 `ValidationError`, `CorporateCard`, `ExpenseItemCreate`·`ExpenseItemUpdate`, `validate_codes`, `assert_item_amount`·`assert_report_total`·`sum_included`를 더한다.

```python
async def _recalc_total(session: AsyncSession, report: ExpenseReport) -> None:
    """비정규화 컬럼 total_amount_krw의 책임자는 서비스다 (모델 주석 참조).

    제외(is_excluded) 항목은 빼고 더한다. 합계 상한을 여기서 보는 이유는 항목 상한만
    두면 항목 여러 개로 컬럼을 넘길 수 있기 때문이다 — 그 오버플로는 flush에서 500이 된다.
    """
    rows = (
        await session.execute(
            select(ExpenseItem.amount_krw, ExpenseItem.is_excluded).where(
                ExpenseItem.report_id == report.id
            )
        )
    ).all()
    total = sum_included([(amount, excluded) for amount, excluded in rows])
    assert_report_total(total)
    report.total_amount_krw = total


async def _load_editable_report(
    session: AsyncSession, *, user: User, report_id: int
) -> ExpenseReport:
    report = await load_visible_report(session, report_id, user)
    assert_report_owner(user_id=user.id, owner_id=report.user_id)
    assert_report_editable(report.status)
    return report


async def _load_item_for_edit(
    session: AsyncSession, *, user: User, item_id: int
) -> tuple[ExpenseItem, ExpenseReport]:
    item = await session.get(ExpenseItem, item_id)
    if item is None:
        raise NotFoundError("EXPENSE_ITEM_NOT_FOUND", "정산 항목을 찾을 수 없습니다")
    # 리포트 가시성 검사를 통과해야 항목의 존재를 알 수 있다. 남의 항목은 404다.
    report = await _load_editable_report(session, user=user, report_id=item.report_id)
    return item, report


async def _assert_usable_transaction(
    session: AsyncSession, *, report: ExpenseReport, transaction_id: int
) -> CardTransaction:
    """정산서 소유자의 카드 거래이고 취소되지 않았을 것."""
    transaction = (
        await session.execute(
            select(CardTransaction)
            .join(CorporateCard, CorporateCard.id == CardTransaction.card_id)
            .where(
                CardTransaction.id == transaction_id,
                CorporateCard.user_id == report.user_id,
                CardTransaction.is_cancelled.is_(False),
            )
        )
    ).scalar_one_or_none()
    if transaction is None:
        raise ValidationError(
            "INVALID_TRANSACTION",
            "정산에 사용할 수 없는 카드 거래입니다",
            field="card_transaction_id",
        )
    duplicated = (
        await session.execute(
            select(ExpenseItem.id).where(
                ExpenseItem.report_id == report.id,
                ExpenseItem.card_transaction_id == transaction_id,
            )
        )
    ).scalar_one_or_none()
    if duplicated is not None:
        # (report_id, card_transaction_id) unique 제약을 flush에서 맞으면 500이 된다.
        raise ConflictError("EXPENSE_ITEM_DUPLICATE", "이미 담은 카드 거래입니다")
    return transaction


async def _validate_item_centers(session: AsyncSession, changes: dict) -> None:
    """항목의 FC/CC는 override이므로 None(상속)은 검증하지 않는다."""
    if changes.get("fund_center_code") is not None:
        await assert_fund_center(session, changes["fund_center_code"])
    if changes.get("cost_center_code") is not None:
        await assert_cost_center(session, changes["cost_center_code"])


async def add_item(
    session: AsyncSession, *, user: User, report_id: int, payload: ExpenseItemCreate
) -> ExpenseReportDetail:
    report = await _load_editable_report(session, user=user, report_id=report_id)
    values = payload.model_dump()

    await validate_codes(
        session,
        [("EXPENSE_CATEGORY", "expense_category_code", values["expense_category_code"])],
    )
    await _validate_item_centers(session, values)

    amount = values["amount_krw"]
    if values["card_transaction_id"] is not None:
        transaction = await _assert_usable_transaction(
            session, report=report, transaction_id=values["card_transaction_id"]
        )
        if amount is None:
            amount = transaction.amount_krw
    elif amount is None:
        raise ValidationError(
            "AMOUNT_REQUIRED", "카드 거래를 연결하지 않으면 금액이 필요합니다", field="amount_krw"
        )
    assert_item_amount(amount)

    session.add(
        ExpenseItem(
            report_id=report.id,
            card_transaction_id=values["card_transaction_id"],
            expense_category_code=values["expense_category_code"],
            amount_krw=amount,
            memo=values["memo"],
            fund_center_code=values["fund_center_code"],
            cost_center_code=values["cost_center_code"],
        )
    )
    await session.flush()
    await _recalc_total(session, report)
    await session.commit()
    return await build_detail(session, report)


async def update_item(
    session: AsyncSession, *, user: User, item_id: int, payload: ExpenseItemUpdate
) -> ExpenseReportDetail:
    item, report = await _load_item_for_edit(session, user=user, item_id=item_id)
    changes = payload.model_dump(exclude_unset=True)

    if "expense_category_code" in changes and changes["expense_category_code"] is not None:
        await validate_codes(
            session,
            [("EXPENSE_CATEGORY", "expense_category_code", changes["expense_category_code"])],
        )
    await _validate_item_centers(session, changes)
    if changes.get("amount_krw") is not None:
        assert_item_amount(changes["amount_krw"])

    for name, value in changes.items():
        setattr(item, name, value)
    await session.flush()
    await _recalc_total(session, report)
    await session.commit()
    return await build_detail(session, report)


async def delete_item(
    session: AsyncSession, *, user: User, item_id: int
) -> ExpenseReportDetail:
    item, report = await _load_item_for_edit(session, user=user, item_id=item_id)
    await session.delete(item)
    await session.flush()
    await _recalc_total(session, report)
    await session.commit()
    return await build_detail(session, report)
```

`ExpenseItemUpdate`에서 `fund_center_code`·`cost_center_code`를 **비우는**(상속으로 되돌리는) 요청은 `null`을 명시적으로 보내면 된다 — `exclude_unset=True`라 보내지 않은 필드는 건드리지 않고, `null`을 보내면 `changes`에 `None`이 들어와 대입된다. `_validate_item_centers`는 `None`을 검증하지 않으므로 그대로 통과한다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_expenses_service_write.py -v`
Expected: PASS (22건)

- [ ] **Step 5: mutation 3건**

| mutation | 기대 |
|---|---|
| `_recalc_total`의 `sum_included(...)` → `sum(amount for amount, _ in rows)` | `test_excluded_items_drop_out_of_the_total` FAIL |
| `_assert_usable_transaction`의 `CorporateCard.user_id == report.user_id` 삭제 | `test_add_item_rejects_someone_elses_transaction` FAIL |
| `assert_item_amount(amount)` 삭제 | `test_item_amount_above_the_column_limit_is_a_400_not_a_500` FAIL (에러가 `ValidationError` 대신 DB 오류로 바뀐다) |

각각 되돌린다.

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/expenses.py backend/tests/test_expenses_service_write.py
git commit -m "feat: add expense item CRUD with total recomputation"
```

---

## Task 12: 자동매칭 후보 엔드포인트용 서비스

**Files:**
- Modify: `backend/app/services/expenses.py`
- Test: `backend/tests/test_expenses_service_write.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_expenses_service_write.py`에 추가:

```python
from app.services.expenses import list_match_candidates


async def _txn_on(db_session, card, day_offset, trip, **kwargs):
    from datetime import timedelta

    when = datetime.combine(
        trip.start_date + timedelta(days=day_offset), datetime.min.time(), tzinfo=timezone.utc
    ) + timedelta(hours=3)  # KST 정오
    return await make_card_transaction(db_session, card=card, approved_at=when, **kwargs)


async def test_match_candidates_come_from_the_owners_cards_within_the_window(db_session):
    _, owner, trip, report, card = await _report_with_card(db_session)
    inside = await _txn_on(db_session, card, 1, trip)
    await _txn_on(db_session, card, 30, trip)  # 창 밖

    candidates = await list_match_candidates(db_session, user=owner, report_id=report.id)

    assert [c.transaction_id for c in candidates] == [inside.id]
    assert candidates[0].reasons == ["출장기간 내 승인"]
    assert candidates[0].suggested_category_code == "MEAL"
    assert candidates[0].already_added is False


async def test_match_candidates_exclude_transactions_locked_by_another_report(db_session):
    manager, owner = await _org(db_session)
    card = await make_card(db_session, user=owner)
    trip_a = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    trip_b = await make_trip(
        db_session,
        user=owner,
        status=TripStatus.COMPLETED,
        approver_id=manager.id,
        start_date=trip_a.start_date,
        end_date=trip_a.end_date,
    )
    report_a = await make_expense_report(
        db_session, trip=trip_a, approver=manager, status=ExpenseReportStatus.SUBMITTED
    )
    report_b = await make_expense_report(db_session, trip=trip_b, approver=manager)
    transaction = await _txn_on(db_session, card, 1, trip_a)
    await make_expense_item(db_session, report=report_a, card_transaction=transaction)

    candidates = await list_match_candidates(db_session, user=owner, report_id=report_b.id)
    assert candidates == []


async def test_a_draft_report_does_not_lock_transactions(db_session):
    """제출완료(SUBMITTED 이상)만 잠근다 (spec 5.6). DRAFT까지 잠그면 다른 정산서를
    임시저장만 해 둔 채로 거래가 사라진다."""
    manager, owner = await _org(db_session)
    card = await make_card(db_session, user=owner)
    trip_a = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    trip_b = await make_trip(
        db_session,
        user=owner,
        status=TripStatus.COMPLETED,
        approver_id=manager.id,
        start_date=trip_a.start_date,
        end_date=trip_a.end_date,
    )
    report_a = await make_expense_report(db_session, trip=trip_a, approver=manager)
    report_b = await make_expense_report(db_session, trip=trip_b, approver=manager)
    transaction = await _txn_on(db_session, card, 1, trip_a)
    await make_expense_item(db_session, report=report_a, card_transaction=transaction)

    candidates = await list_match_candidates(db_session, user=owner, report_id=report_b.id)
    assert [c.transaction_id for c in candidates] == [transaction.id]


async def test_already_added_transactions_are_marked_not_hidden(db_session):
    _, owner, trip, report, card = await _report_with_card(db_session)
    transaction = await _txn_on(db_session, card, 1, trip)
    await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(
            card_transaction_id=transaction.id, expense_category_code="MEAL"
        ),
    )
    [candidate] = await list_match_candidates(db_session, user=owner, report_id=report.id)
    assert candidate.transaction_id == transaction.id
    assert candidate.already_added is True


async def test_approver_can_read_match_candidates(db_session):
    manager, owner, trip, report, card = await _report_with_card(db_session)
    await _txn_on(db_session, card, 1, trip)
    candidates = await list_match_candidates(db_session, user=manager, report_id=report.id)
    assert len(candidates) == 1
```

`make_expense_item` import를 파일 상단 factories import에 추가한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_expenses_service_write.py -k match -v`
Expected: FAIL — `ImportError: cannot import name 'list_match_candidates'`

- [ ] **Step 3: 구현한다**

`backend/app/services/expenses.py`에 추가한다 (import에 `timedelta`, `MatchCandidateOut`, `TransactionView`·`find_candidates`, `CorporateCard`를 더한다):

```python
#: 조회 창은 매칭 창(±1일)보다 하루 더 넓게 잡는다. KST 변환으로 경계가 최대 하루
#: 움직이므로, 정확한 경계 판정은 순수 함수(find_candidates)에 맡기고 여기서는
#: 넉넉히 읽어온다.
_FETCH_MARGIN_DAYS = 2


async def list_match_candidates(
    session: AsyncSession, *, user: User, report_id: int
) -> list[MatchCandidateOut]:
    """자동매칭 후보 + 사유 (spec 5.6).

    "누구 카드인가"와 "다른 제출완료 리포트가 가져갔는가"는 조회가 필요하므로 여기서
    거른 뒤, 창·취소·사유 판정은 DB를 모르는 `matching.find_candidates`에 넘긴다.
    """
    report = await load_visible_report(session, report_id, user)
    trip = await session.get(Trip, report.trip_id)

    rows = (
        (
            await session.execute(
                select(CardTransaction)
                .join(CorporateCard, CorporateCard.id == CardTransaction.card_id)
                .where(
                    CorporateCard.user_id == report.user_id,
                    CardTransaction.approved_at
                    >= datetime.combine(
                        trip.start_date - timedelta(days=_FETCH_MARGIN_DAYS),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                    CardTransaction.approved_at
                    < datetime.combine(
                        trip.end_date + timedelta(days=_FETCH_MARGIN_DAYS + 1),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )

    # 다른 리포트가 제출완료(SUBMITTED 이상)로 이미 가져간 거래는 후보에서 뺀다.
    locked = set(
        (
            await session.execute(
                select(ExpenseItem.card_transaction_id)
                .join(ExpenseReport, ExpenseReport.id == ExpenseItem.report_id)
                .where(
                    ExpenseItem.card_transaction_id.is_not(None),
                    ExpenseReport.id != report.id,
                    ExpenseReport.status.in_(
                        [ExpenseReportStatus.SUBMITTED, ExpenseReportStatus.APPROVED]
                    ),
                )
            )
        ).scalars()
    )
    # 이 리포트가 이미 담은 거래는 숨기지 않고 표시만 한다 — 화면에서 "담김"으로 보여야
    # 사용자가 후보 목록과 항목 목록을 대조할 수 있다.
    added = set(
        (
            await session.execute(
                select(ExpenseItem.card_transaction_id).where(
                    ExpenseItem.report_id == report.id,
                    ExpenseItem.card_transaction_id.is_not(None),
                )
            )
        ).scalars()
    )

    by_id = {row.id: row for row in rows}
    candidates = find_candidates(
        start_date=trip.start_date,
        end_date=trip.end_date,
        transactions=[
            TransactionView(
                id=row.id,
                approved_at=row.approved_at,
                merchant_category_code=row.merchant_category_code,
                amount_krw=row.amount_krw,
                is_cancelled=row.is_cancelled,
            )
            for row in rows
        ],
        excluded_transaction_ids=frozenset(locked),
    )
    return [
        MatchCandidateOut(
            transaction_id=candidate.transaction_id,
            approved_at=by_id[candidate.transaction_id].approved_at,
            merchant_name=by_id[candidate.transaction_id].merchant_name,
            merchant_category_code=by_id[candidate.transaction_id].merchant_category_code,
            amount_krw=by_id[candidate.transaction_id].amount_krw,
            suggested_category_code=candidate.suggested_category_code,
            reasons=list(candidate.reasons),
            already_added=candidate.transaction_id in added,
        )
        for candidate in candidates
    ]
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_expenses_service_write.py -v`
Expected: PASS (27건)

- [ ] **Step 5: mutation 2건**

| mutation | 기대 |
|---|---|
| `ExpenseReport.status.in_([SUBMITTED, APPROVED])` → `.in_([DRAFT, SUBMITTED, APPROVED])` | `test_a_draft_report_does_not_lock_transactions` FAIL |
| `ExpenseReport.id != report.id` 삭제 | `test_already_added_transactions_are_marked_not_hidden`이 SUBMITTED 리포트에서 후보를 잃는다 — 확인 후 되돌린다 (현재 테스트가 DRAFT라 통과할 수 있다. 통과하면 이 조건을 지키는 테스트를 하나 더 쓴다: SUBMITTED 상태의 리포트에서 자기 항목이 여전히 후보로 보이는지) |

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/expenses.py backend/tests/test_expenses_service_write.py
git commit -m "feat: add match candidate lookup wiring the pure matcher to the DB"
```

---

## Task 13: `settle_trip_for_report` — 출장의 시스템 전이

**Files:**
- Modify: `backend/app/services/trips.py`
- Test: `backend/tests/test_trips_service_transitions.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_trips_service_transitions.py`에 추가:

```python
from app.enums import EntityType
from app.models import ActivityLog
from app.services.trips import settle_trip_for_report


async def test_settle_trip_for_report_moves_completed_to_settled(db_session):
    manager, owner = await _org(db_session)  # 이 파일에 이미 있는 헬퍼를 쓴다
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )

    await settle_trip_for_report(
        db_session, trip=trip, actor_id=manager.id, report_no="EX-9999-0001"
    )

    assert trip.status is TripStatus.SETTLED


async def test_settle_trip_for_report_records_the_trip_timeline(db_session):
    """출장 쪽 이력이 비면 타임라인이 COMPLETED에서 끊긴다."""
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    await settle_trip_for_report(
        db_session, trip=trip, actor_id=manager.id, report_no="EX-9999-0002"
    )

    rows = (
        (
            await db_session.execute(
                select(ActivityLog).where(
                    ActivityLog.entity_type == EntityType.TRIP,
                    ActivityLog.entity_id == trip.id,
                )
            )
        )
        .scalars()
        .all()
    )
    settled = [row for row in rows if row.to_status == TripStatus.SETTLED.value]
    assert len(settled) == 1
    assert settled[0].from_status == TripStatus.COMPLETED.value
    assert "EX-9999-0002" in settled[0].memo


async def test_settle_trip_for_report_rejects_a_trip_that_is_not_completed(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.APPROVED, approver_id=manager.id
    )
    with pytest.raises(ConflictError) as excinfo:
        await settle_trip_for_report(
            db_session, trip=trip, actor_id=manager.id, report_no="EX-9999-0003"
        )
    assert excinfo.value.code == "TRIP_INVALID_TRANSITION"
    assert trip.status is TripStatus.APPROVED
```

`_org` 헬퍼가 이 파일에 없으면 `make_user`로 매니저·소유자를 만드는 두 줄을 각 테스트에 인라인한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_trips_service_transitions.py -k settle -v`
Expected: FAIL — `ImportError: cannot import name 'settle_trip_for_report'`

- [ ] **Step 3: 구현한다**

`backend/app/services/trips.py`에 추가한다. import에 `assert_system_transition`을 더한다:

```python
async def settle_trip_for_report(
    session: AsyncSession, *, trip: Trip, actor_id: int, report_no: str
) -> None:
    """정산서 승인이 트리거하는 COMPLETED → SETTLED (spec 5.4).

    commit하지 않는다 — 정산서 승인과 **같은 트랜잭션**에서 끝나야 한다. 따로 커밋하면
    정산서는 승인됐는데 출장은 COMPLETED로 남는 상태가 만들어질 수 있다.

    사용자 경로(`assert_transition_allowed`)로는 이 전이를 통과할 수 없고, 반대로 이
    함수는 사용자 주체 전이를 거부한다.
    """
    assert_system_transition(trip.status, TripStatus.SETTLED)

    from_status = trip.status
    trip.status = TripStatus.SETTLED
    await session.flush()
    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=actor_id,
        action=ActivityAction.SETTLED,
        from_status=from_status.value,
        to_status=TripStatus.SETTLED.value,
        # 알림은 정산서 쪽에서 EXPENSE_APPROVED 하나만 보낸다. 한 번의 승인으로 알림
        # 두 개를 받을 이유가 없고, NotificationType에 TRIP_SETTLED도 없다.
        memo=f"정산서 {report_no} 승인으로 정산 완료",
    )
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_trips_service_transitions.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/trips.py backend/tests/test_trips_service_transitions.py
git commit -m "feat: settle a trip when its expense report is approved"
```

---

## Task 14: 정산서 전이 4종 + 타임라인

**Files:**
- Modify: `backend/app/services/expenses.py`
- Test: `backend/tests/test_expenses_service_transitions.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_expenses_service_transitions.py`:

```python
"""정산서 상태 전이. 출장의 전이 테스트와 같은 구조를 유지한다."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.enums import (
    ActivityAction,
    EntityType,
    ExpenseReportStatus,
    NotificationType,
    TripStatus,
    UserRole,
)
from app.errors import ConflictError, ForbiddenError, ValidationError
from app.models import ActivityLog, Notification
from app.schemas.expense import ExpenseItemCreate, ExpenseReportUpdate
from app.schemas.trip import RejectRequest
from app.services.expenses import (
    add_item,
    approve_report,
    list_report_timeline,
    reject_report,
    reopen_report,
    submit_report,
    update_report,
)
from tests.factories import (
    make_card,
    make_card_transaction,
    make_expense_report,
    make_trip,
    make_trip_master_data,
    make_user,
)


async def _ready_report(db_session, *, trip_status=TripStatus.COMPLETED, with_centers=True):
    """제출 직전 상태의 정산서를 만든다 — 항목 1건 + FC/CC 지정."""
    await make_trip_master_data(db_session)
    manager = await make_user(db_session, role=UserRole.MANAGER, name="김결재")
    owner = await make_user(db_session, manager=manager, name="박신청")
    trip = await make_trip(
        db_session, user=owner, status=trip_status, approver_id=manager.id
    )
    report = await make_expense_report(
        db_session, trip=trip, approver=manager, fund_center_code=None
    )
    card = await make_card(db_session, user=owner)
    await make_card_transaction(
        db_session,
        card=card,
        approved_at=datetime.combine(
            trip.start_date, datetime.min.time(), tzinfo=timezone.utc
        )
        + timedelta(hours=3),
    )
    await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("30000")),
    )
    if with_centers:
        await update_report(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseReportUpdate(fund_center_code="FC1010", cost_center_code="CC2030"),
        )
    return manager, owner, trip, report


async def test_submit_moves_to_submitted_and_notifies_the_approver(db_session):
    manager, owner, _, report = await _ready_report(db_session)

    detail = await submit_report(db_session, user=owner, report_id=report.id)

    assert detail.status is ExpenseReportStatus.SUBMITTED
    assert detail.submitted_at is not None
    assert detail.approver_id == manager.id

    notifications = (
        (
            await db_session.execute(
                select(Notification).where(Notification.user_id == manager.id)
            )
        )
        .scalars()
        .all()
    )
    assert [n.type for n in notifications] == [NotificationType.EXPENSE_SUBMITTED]


async def test_submit_requires_a_fund_center(db_session):
    _, owner, _, report = await _ready_report(db_session, with_centers=False)
    with pytest.raises(ValidationError) as excinfo:
        await submit_report(db_session, user=owner, report_id=report.id)
    assert excinfo.value.code == "CENTER_REQUIRED"
    assert excinfo.value.field == "fund_center_code"


async def test_submit_requires_a_completed_trip(db_session):
    _, owner, _, report = await _ready_report(db_session, trip_status=TripStatus.APPROVED)
    with pytest.raises(ConflictError) as excinfo:
        await submit_report(db_session, user=owner, report_id=report.id)
    assert excinfo.value.code == "TRIP_NOT_COMPLETED"


async def test_submit_requires_at_least_one_included_item(db_session):
    await make_trip_master_data(db_session)
    manager = await make_user(db_session, role=UserRole.MANAGER)
    owner = await make_user(db_session, manager=manager)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(db_session, trip=trip, approver=manager)
    await update_report(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseReportUpdate(fund_center_code="FC1010", cost_center_code="CC2030"),
    )
    with pytest.raises(ConflictError) as excinfo:
        await submit_report(db_session, user=owner, report_id=report.id)
    assert excinfo.value.code == "EXPENSE_NO_ITEMS"


async def test_the_approver_cannot_submit(db_session):
    manager, _, _, report = await _ready_report(db_session)
    with pytest.raises(ForbiddenError) as excinfo:
        await submit_report(db_session, user=manager, report_id=report.id)
    assert excinfo.value.code == "NOT_EXPENSE_OWNER"


async def test_double_submit_is_a_409(db_session):
    _, owner, _, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)
    with pytest.raises(ConflictError) as excinfo:
        await submit_report(db_session, user=owner, report_id=report.id)
    assert excinfo.value.code == "EXPENSE_INVALID_TRANSITION"


async def test_approve_settles_the_trip_and_notifies_the_owner(db_session):
    manager, owner, trip, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)

    detail = await approve_report(db_session, user=manager, report_id=report.id)

    assert detail.status is ExpenseReportStatus.APPROVED
    assert detail.approved_at is not None

    await db_session.refresh(trip)
    assert trip.status is TripStatus.SETTLED

    notifications = (
        (
            await db_session.execute(
                select(Notification).where(Notification.user_id == owner.id)
            )
        )
        .scalars()
        .all()
    )
    assert [n.type for n in notifications] == [NotificationType.EXPENSE_APPROVED]

    trip_log = (
        (
            await db_session.execute(
                select(ActivityLog).where(
                    ActivityLog.entity_type == EntityType.TRIP,
                    ActivityLog.entity_id == trip.id,
                    ActivityLog.action == ActivityAction.SETTLED,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(trip_log) == 1


async def test_the_owner_cannot_approve(db_session):
    _, owner, _, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)
    with pytest.raises(ForbiddenError) as excinfo:
        await approve_report(db_session, user=owner, report_id=report.id)
    assert excinfo.value.code == "NOT_EXPENSE_APPROVER"


async def test_reject_requires_a_reason_and_notifies_the_owner(db_session):
    manager, owner, _, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)

    with pytest.raises(ValidationError) as excinfo:
        await reject_report(
            db_session, user=manager, report_id=report.id, payload=RejectRequest(reason="  ")
        )
    assert excinfo.value.code == "REJECT_REASON_REQUIRED"

    detail = await reject_report(
        db_session,
        user=manager,
        report_id=report.id,
        payload=RejectRequest(reason="영수증 누락"),
    )
    assert detail.status is ExpenseReportStatus.REJECTED
    assert detail.reject_reason == "영수증 누락"

    notifications = (
        (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == owner.id,
                    Notification.type == NotificationType.EXPENSE_REJECTED,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(notifications) == 1


async def test_rejected_report_can_be_reopened_and_resubmitted(db_session):
    manager, owner, _, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)
    await reject_report(
        db_session, user=manager, report_id=report.id, payload=RejectRequest(reason="보완")
    )

    detail = await reopen_report(db_session, user=owner, report_id=report.id)
    assert detail.status is ExpenseReportStatus.DRAFT
    assert detail.submitted_at is None
    # 무엇을 고쳐야 하는지 화면에 계속 보여야 하므로 반려 사유는 남긴다.
    assert detail.reject_reason == "보완"

    detail = await submit_report(db_session, user=owner, report_id=report.id)
    assert detail.status is ExpenseReportStatus.SUBMITTED
    assert detail.reject_reason is None


async def test_an_approved_report_is_terminal(db_session):
    manager, owner, _, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)
    await approve_report(db_session, user=manager, report_id=report.id)
    with pytest.raises(ConflictError):
        await reopen_report(db_session, user=owner, report_id=report.id)


async def test_timeline_lists_the_report_history_in_order(db_session):
    manager, owner, _, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)
    await approve_report(db_session, user=manager, report_id=report.id)

    entries = await list_report_timeline(db_session, user=owner, report_id=report.id)
    actions = [entry.action for entry in entries]
    assert actions[0] is ActivityAction.UPDATED or actions[0] is ActivityAction.CREATED
    assert ActivityAction.SUBMITTED in actions
    assert ActivityAction.APPROVED in actions
    assert all(entry.actor_name for entry in entries)
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_expenses_service_transitions.py -v`
Expected: FAIL — `ImportError: cannot import name 'submit_report'`

- [ ] **Step 3: 구현한다**

`backend/app/services/expenses.py`에 추가한다. import에 `ActivityLog`, `NotificationType`, `TimelineEntry`, `RejectRequest`, `NotifySpec`, `assert_centers_present`·`assert_expense_transition_allowed`·`assert_has_items`·`assert_trip_completed`, `assert_has_approver`·`assert_reject_reason`(trip_rules), `settle_trip_for_report`를 더한다.

```python
def _link(report: ExpenseReport) -> str:
    return f"/expenses/{report.id}"


def _assert_transition(
    report: ExpenseReport, user: User, target: ExpenseReportStatus
) -> None:
    """전이 검사는 이 한 줄만 부른다 — 출장 쪽 `_assert_transition`과 같은 이유다.
    적법성과 주체를 따로 부를 수 있게 열어두면 언젠가 한쪽만 부르고 그 실패는 조용하다.
    """
    assert_expense_transition_allowed(
        report.status,
        target,
        user_id=user.id,
        owner_id=report.user_id,
        approver_id=report.approver_id,
    )


async def submit_report(
    session: AsyncSession, *, user: User, report_id: int
) -> ExpenseReportDetail:
    report = await load_visible_report(session, report_id, user)
    _assert_transition(report, user, ExpenseReportStatus.SUBMITTED)

    trip = await session.get(Trip, report.trip_id)
    assert_trip_completed(trip.status)

    assert_centers_present(
        fund_center_code=report.fund_center_code, cost_center_code=report.cost_center_code
    )
    # 마스터가 그 사이 비활성화됐을 수 있다. 제출은 마지막 검증 지점이다.
    await assert_fund_center(session, report.fund_center_code)
    await assert_cost_center(session, report.cost_center_code)

    included = (
        await session.execute(
            select(func.count())
            .select_from(ExpenseItem)
            .where(ExpenseItem.report_id == report.id, ExpenseItem.is_excluded.is_(False))
        )
    ).scalar_one()
    assert_has_items(included)
    await _recalc_total(session, report)

    approver_id = assert_has_approver(trip.approver_id)
    from_status = report.status
    report.status = ExpenseReportStatus.SUBMITTED
    report.approver_id = approver_id
    report.submitted_at = datetime.now(timezone.utc)
    report.approved_at = None
    report.reject_reason = None
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.EXPENSE_REPORT,
        entity_id=report.id,
        actor_id=user.id,
        action=ActivityAction.SUBMITTED,
        from_status=from_status.value,
        to_status=ExpenseReportStatus.SUBMITTED.value,
        notify=NotifySpec(
            user_id=approver_id,
            type=NotificationType.EXPENSE_SUBMITTED,
            title="정산 결재 요청",
            body=f"{user.name}님이 '{trip.title}' 출장의 정산서를 상신했습니다.",
            link_url=_link(report),
        ),
    )
    await session.commit()
    return await build_detail(session, report)


async def approve_report(
    session: AsyncSession, *, user: User, report_id: int
) -> ExpenseReportDetail:
    report = await load_visible_report(session, report_id, user)
    _assert_transition(report, user, ExpenseReportStatus.APPROVED)

    trip = await session.get(Trip, report.trip_id)
    from_status = report.status
    report.status = ExpenseReportStatus.APPROVED
    report.approved_at = datetime.now(timezone.utc)
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.EXPENSE_REPORT,
        entity_id=report.id,
        actor_id=user.id,
        action=ActivityAction.APPROVED,
        from_status=from_status.value,
        to_status=ExpenseReportStatus.APPROVED.value,
        notify=NotifySpec(
            user_id=report.user_id,
            type=NotificationType.EXPENSE_APPROVED,
            title="정산이 승인되었습니다",
            body=f"'{trip.title}' 출장의 정산서가 승인되어 정산 완료 처리되었습니다.",
            link_url=_link(report),
        ),
    )
    # 같은 트랜잭션에서 출장을 SETTLED로 보낸다. 여기서 실패하면 정산서 승인도 함께
    # 롤백되는 것이 옳다 — 정산 완료인데 출장은 COMPLETED인 상태를 만들지 않는다.
    await settle_trip_for_report(
        session, trip=trip, actor_id=user.id, report_no=report.report_no
    )
    await session.commit()
    return await build_detail(session, report)


async def reject_report(
    session: AsyncSession, *, user: User, report_id: int, payload: RejectRequest
) -> ExpenseReportDetail:
    report = await load_visible_report(session, report_id, user)
    _assert_transition(report, user, ExpenseReportStatus.REJECTED)
    reason = assert_reject_reason(payload.reason)

    trip = await session.get(Trip, report.trip_id)
    from_status = report.status
    report.status = ExpenseReportStatus.REJECTED
    report.reject_reason = reason
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.EXPENSE_REPORT,
        entity_id=report.id,
        actor_id=user.id,
        action=ActivityAction.REJECTED,
        from_status=from_status.value,
        to_status=ExpenseReportStatus.REJECTED.value,
        memo=reason,
        notify=NotifySpec(
            user_id=report.user_id,
            type=NotificationType.EXPENSE_REJECTED,
            title="정산서가 반려되었습니다",
            body=f"'{trip.title}' 출장의 정산서가 반려되었습니다. 사유: {reason}",
            link_url=_link(report),
        ),
    )
    await session.commit()
    return await build_detail(session, report)


async def reopen_report(
    session: AsyncSession, *, user: User, report_id: int
) -> ExpenseReportDetail:
    """반려된 정산서를 임시저장으로 되돌린다 (출장의 reopen_trip과 같은 이유).

    이것이 없으면 반려된 정산서는 영원히 반려 상태로 남는다.
    """
    report = await load_visible_report(session, report_id, user)
    _assert_transition(report, user, ExpenseReportStatus.DRAFT)

    from_status = report.status
    report.status = ExpenseReportStatus.DRAFT
    report.submitted_at = None
    report.approved_at = None
    # reject_reason은 남긴다 — 다음 상신에서 submit_report가 지운다.
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.EXPENSE_REPORT,
        entity_id=report.id,
        actor_id=user.id,
        action=ActivityAction.UPDATED,
        from_status=from_status.value,
        to_status=ExpenseReportStatus.DRAFT.value,
        memo="재작성을 위해 임시저장으로 되돌림",
    )
    await session.commit()
    return await build_detail(session, report)


async def list_report_timeline(
    session: AsyncSession, *, user: User, report_id: int
) -> list[TimelineEntry]:
    report = await load_visible_report(session, report_id, user)
    rows = (
        (
            await session.execute(
                select(ActivityLog)
                .where(
                    ActivityLog.entity_type == EntityType.EXPENSE_REPORT,
                    ActivityLog.entity_id == report.id,
                )
                .order_by(ActivityLog.created_at, ActivityLog.id)
            )
        )
        .scalars()
        .all()
    )
    names = await load_user_names(session, {row.actor_id for row in rows})
    return [
        TimelineEntry(
            id=row.id,
            action=row.action,
            from_status=row.from_status,
            to_status=row.to_status,
            memo=row.memo,
            actor_id=row.actor_id,
            actor_name=names.get(row.actor_id, ""),
            created_at=row.created_at,
        )
        for row in rows
    ]
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_expenses_service_transitions.py -v`
Expected: PASS (12건)

- [ ] **Step 5: mutation 3건**

| mutation | 기대 |
|---|---|
| `assert_trip_completed(trip.status)` 삭제 | `test_submit_requires_a_completed_trip` FAIL |
| `assert_centers_present(...)` 삭제 | `test_submit_requires_a_fund_center` FAIL |
| `settle_trip_for_report(...)` 호출 삭제 | `test_approve_settles_the_trip_and_notifies_the_owner` FAIL |

각각 되돌린다.

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/expenses.py backend/tests/test_expenses_service_transitions.py
git commit -m "feat: add expense report transitions and timeline"
```

---

## Task 15: 정산 라우터 + API 계약 테스트

**Files:**
- Create: `backend/app/routers/expenses.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_expenses_api.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_expenses_api.py`:

```python
"""정산 API 계약. 시드 데이터 + JWT로 사람이 하는 순서를 그대로 밟는다.

같은 엔드포인트를 Agent가 쓰는 것이 이 프로젝트의 핵심 메시지이므로, 에러 바디의
code·field까지 단언한다.
"""

from app.enums import TripStatus


async def _completed_trip_without_report(client, headers):
    """정산서가 아직 없는 COMPLETED 출장을 찾는다. 시드는 COMPLETED 9건 중 일부에만
    정산서를 만들어 둔다."""
    trips = (await client.get("/api/v1/trips?status=COMPLETED&size=50", headers=headers)).json()
    expenses = (await client.get("/api/v1/expenses?size=100", headers=headers)).json()
    taken = {item["trip_id"] for item in expenses["items"]}
    for trip in trips["items"]:
        if trip["id"] not in taken:
            return trip
    raise AssertionError("정산서가 없는 COMPLETED 출장이 시드에 없습니다")


async def test_full_expense_flow_over_http(client, login_as, seeded):
    owner_headers = await login_as("user1@skon.example")
    trip = await _completed_trip_without_report(client, owner_headers)

    created = await client.post(
        "/api/v1/expenses", json={"trip_id": trip["id"]}, headers=owner_headers
    )
    assert created.status_code == 201, created.text
    report = created.json()
    assert report["status"] == "DRAFT"
    assert report["cost_center_code"] == trip["cost_center_code"]
    report_id = report["id"]

    candidates = await client.get(
        f"/api/v1/expenses/{report_id}/match-candidates", headers=owner_headers
    )
    assert candidates.status_code == 200
    rows = candidates.json()
    assert rows, "시드는 완료 출장 기간에 카드거래를 만들어 둔다"
    assert rows[0]["reasons"]

    added = await client.post(
        f"/api/v1/expenses/{report_id}/items",
        json={
            "card_transaction_id": rows[0]["transaction_id"],
            "expense_category_code": rows[0]["suggested_category_code"],
        },
        headers=owner_headers,
    )
    assert added.status_code == 201, added.text
    assert added.json()["total_amount_krw"] == rows[0]["amount_krw"]

    patched = await client.patch(
        f"/api/v1/expenses/{report_id}",
        json={"fund_center_code": "FC1010"},
        headers=owner_headers,
    )
    assert patched.status_code == 200

    submitted = await client.post(
        f"/api/v1/expenses/{report_id}/submit", headers=owner_headers
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "SUBMITTED"

    approver_headers = await login_as("manager1@skon.example")
    inbox = await client.get("/api/v1/expenses?scope=approvals", headers=approver_headers)
    assert any(item["id"] == report_id for item in inbox.json()["items"])

    approved = await client.post(
        f"/api/v1/expenses/{report_id}/approve", headers=approver_headers
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    settled = await client.get(f"/api/v1/trips/{trip['id']}", headers=owner_headers)
    assert settled.json()["status"] == TripStatus.SETTLED.value

    timeline = await client.get(f"/api/v1/trips/{trip['id']}/timeline", headers=owner_headers)
    assert any(entry["to_status"] == "SETTLED" for entry in timeline.json())


async def test_creating_a_report_twice_returns_409_with_a_machine_readable_code(
    client, login_as, seeded
):
    headers = await login_as("user1@skon.example")
    trip = await _completed_trip_without_report(client, headers)
    first = await client.post("/api/v1/expenses", json={"trip_id": trip["id"]}, headers=headers)
    assert first.status_code == 201
    second = await client.post("/api/v1/expenses", json={"trip_id": trip["id"]}, headers=headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "EXPENSE_ALREADY_EXISTS"


async def test_submitting_without_a_fund_center_returns_400_with_the_field(
    client, login_as, seeded
):
    headers = await login_as("user1@skon.example")
    trip = await _completed_trip_without_report(client, headers)
    report_id = (
        await client.post("/api/v1/expenses", json={"trip_id": trip["id"]}, headers=headers)
    ).json()["id"]
    await client.post(
        f"/api/v1/expenses/{report_id}/items",
        json={"expense_category_code": "MEAL", "amount_krw": "12000"},
        headers=headers,
    )
    response = await client.post(f"/api/v1/expenses/{report_id}/submit", headers=headers)
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "CENTER_REQUIRED"
    assert body["field"] == "fund_center_code"


async def test_someone_elses_report_is_a_404(client, login_as, seeded):
    owner_headers = await login_as("user1@skon.example")
    trip = await _completed_trip_without_report(client, owner_headers)
    report_id = (
        await client.post(
            "/api/v1/expenses", json={"trip_id": trip["id"]}, headers=owner_headers
        )
    ).json()["id"]

    stranger_headers = await login_as("user2@skon.example")
    response = await client.get(f"/api/v1/expenses/{report_id}", headers=stranger_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXPENSE_NOT_FOUND"


async def test_item_delete_returns_the_updated_report(client, login_as, seeded):
    headers = await login_as("user1@skon.example")
    trip = await _completed_trip_without_report(client, headers)
    report_id = (
        await client.post("/api/v1/expenses", json={"trip_id": trip["id"]}, headers=headers)
    ).json()["id"]
    item_id = (
        await client.post(
            f"/api/v1/expenses/{report_id}/items",
            json={"expense_category_code": "MEAL", "amount_krw": "12000"},
            headers=headers,
        )
    ).json()["items"][0]["id"]

    response = await client.delete(f"/api/v1/expense-items/{item_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total_amount_krw"] == "0.00"


async def test_expense_endpoints_require_authentication(client):
    for method, path in [
        ("get", "/api/v1/expenses"),
        ("post", "/api/v1/expenses"),
        ("get", "/api/v1/expenses/1"),
        ("get", "/api/v1/expenses/1/match-candidates"),
    ]:
        response = await getattr(client, method)(path, json={} if method == "post" else None)
        assert response.status_code == 401, path
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_expenses_api.py -v`
Expected: FAIL — 404 (라우터 없음)

- [ ] **Step 3: 라우터를 구현하고 등록한다**

`backend/app/routers/expenses.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import CurrentUser, DbSession
from app.enums import ExpenseReportStatus
from app.schemas.common import Page
from app.schemas.expense import (
    ExpenseItemCreate,
    ExpenseItemUpdate,
    ExpenseReportCreate,
    ExpenseReportDetail,
    ExpenseReportListItem,
    ExpenseReportUpdate,
    MatchCandidateOut,
)
from app.schemas.trip import RejectRequest, TimelineEntry
from app.services import expenses as expense_service

router = APIRouter(prefix="/api/v1", tags=["expenses"])


@router.get("/expenses", response_model=Page[ExpenseReportListItem])
async def list_expenses(
    user: CurrentUser,
    session: DbSession,
    scope: Annotated[str, Query(pattern="^(mine|approvals|all)$")] = "mine",
    # 파라미터 이름을 status로 두면 fastapi.status 모듈과 충돌한다. 쿼리스트링은 그대로다.
    status_: Annotated[list[ExpenseReportStatus] | None, Query(alias="status")] = None,
    q: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ExpenseReportListItem]:
    return await expense_service.list_reports(
        session,
        user=user,
        filters=expense_service.ExpenseFilters(
            scope=scope, status=status_ or [], q=q, page=page, size=size
        ),
    )


@router.post(
    "/expenses", response_model=ExpenseReportDetail, status_code=status.HTTP_201_CREATED
)
async def create_expense(
    payload: ExpenseReportCreate, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.create_report(session, user=user, payload=payload)


@router.get("/expenses/{report_id}", response_model=ExpenseReportDetail)
async def get_expense(
    report_id: int, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.get_report(session, user=user, report_id=report_id)


@router.patch("/expenses/{report_id}", response_model=ExpenseReportDetail)
async def update_expense(
    report_id: int, payload: ExpenseReportUpdate, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.update_report(
        session, user=user, report_id=report_id, payload=payload
    )


@router.get("/expenses/{report_id}/match-candidates", response_model=list[MatchCandidateOut])
async def list_match_candidates(
    report_id: int, user: CurrentUser, session: DbSession
) -> list[MatchCandidateOut]:
    return await expense_service.list_match_candidates(session, user=user, report_id=report_id)


@router.get("/expenses/{report_id}/timeline", response_model=list[TimelineEntry])
async def get_expense_timeline(
    report_id: int, user: CurrentUser, session: DbSession
) -> list[TimelineEntry]:
    return await expense_service.list_report_timeline(session, user=user, report_id=report_id)


@router.post(
    "/expenses/{report_id}/items",
    response_model=ExpenseReportDetail,
    status_code=status.HTTP_201_CREATED,
)
async def add_expense_item(
    report_id: int, payload: ExpenseItemCreate, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.add_item(
        session, user=user, report_id=report_id, payload=payload
    )


@router.patch("/expense-items/{item_id}", response_model=ExpenseReportDetail)
async def update_expense_item(
    item_id: int, payload: ExpenseItemUpdate, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.update_item(
        session, user=user, item_id=item_id, payload=payload
    )


@router.delete("/expense-items/{item_id}", response_model=ExpenseReportDetail)
async def delete_expense_item(
    item_id: int, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    """204가 아니라 갱신된 정산서를 돌려준다 — 합계와 항목 목록이 함께 바뀌므로
    호출자가 곧바로 다시 GET 해야 하는 왕복을 없앤다."""
    return await expense_service.delete_item(session, user=user, item_id=item_id)


@router.post("/expenses/{report_id}/submit", response_model=ExpenseReportDetail)
async def submit_expense(
    report_id: int, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.submit_report(session, user=user, report_id=report_id)


@router.post("/expenses/{report_id}/approve", response_model=ExpenseReportDetail)
async def approve_expense(
    report_id: int, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.approve_report(session, user=user, report_id=report_id)


@router.post("/expenses/{report_id}/reject", response_model=ExpenseReportDetail)
async def reject_expense(
    report_id: int, payload: RejectRequest, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.reject_report(
        session, user=user, report_id=report_id, payload=payload
    )


@router.post("/expenses/{report_id}/reopen", response_model=ExpenseReportDetail)
async def reopen_expense(
    report_id: int, user: CurrentUser, session: DbSession
) -> ExpenseReportDetail:
    return await expense_service.reopen_report(session, user=user, report_id=report_id)
```

`backend/app/main.py`: import에 `expenses`를 더하고 `app.include_router(expenses.router)`를 추가한다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_expenses_api.py -v`
Expected: PASS (6건)

- [ ] **Step 5: 전체 백엔드 테스트를 돌린다**

Run: `cd backend && uv run pytest -q`
Expected: 전부 PASS (약 360건)

- [ ] **Step 6: OpenAPI가 깨지지 않는지 확인한다**

Run: `cd backend && uv run python -c "from app.main import app; paths=[p for p in app.openapi()['paths'] if 'expense' in p or 'card' in p]; print(sorted(paths))"`
Expected: 12개 경로가 모두 나온다 (`/api/v1/cards`, `/api/v1/card-transactions`, `/api/v1/expenses`, `/api/v1/expenses/{report_id}`, `.../items`, `.../match-candidates`, `.../timeline`, `.../submit`, `.../approve`, `.../reject`, `.../reopen`, `/api/v1/expense-items/{item_id}`)

- [ ] **Step 7: 커밋**

```bash
git add backend/app/routers/expenses.py backend/app/main.py backend/tests/test_expenses_api.py
git commit -m "feat: expose expense endpoints"
```

---

## Task 16: 프론트 타입 · API 클라이언트 · 순수 유틸

**Files:**
- Create: `frontend/src/lib/api/query.ts`, `frontend/src/lib/api/cards.ts`, `frontend/src/lib/api/expenses.ts`, `frontend/src/lib/expenses.ts`, `frontend/src/lib/expenses.test.ts`, `frontend/src/lib/api/query.test.ts`
- Modify: `frontend/src/lib/api/types.ts`, `frontend/src/lib/api/trips.ts`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/src/lib/api/query.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { toQueryString } from './query';

describe('toQueryString', () => {
	it('returns an empty string for an empty query', () => {
		expect(toQueryString({})).toBe('');
	});

	it('repeats array values so the backend reads them as a list', () => {
		expect(toQueryString({ status: ['SUBMITTED', 'APPROVED'] })).toBe(
			'?status=SUBMITTED&status=APPROVED'
		);
	});

	it('drops undefined, null and empty string values', () => {
		expect(toQueryString({ q: '', card_id: undefined, page: 2 })).toBe('?page=2');
	});

	it('keeps false so a boolean filter can be turned off explicitly', () => {
		expect(toQueryString({ include_cancelled: false })).toBe('?include_cancelled=false');
	});
});
```

`frontend/src/lib/expenses.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { EXPENSE_STATUS_LABELS, resolveCenter, sumIncluded } from './expenses';

describe('resolveCenter', () => {
	it('uses the item override when present', () => {
		expect(resolveCenter('CC2040', 'CC2030')).toEqual({ code: 'CC2040', inherited: false });
	});

	it('falls back to the report value and marks it inherited', () => {
		expect(resolveCenter(null, 'CC2030')).toEqual({ code: 'CC2030', inherited: true });
	});

	it('reports nothing when neither level has a value', () => {
		expect(resolveCenter(null, null)).toEqual({ code: null, inherited: true });
	});
});

describe('sumIncluded', () => {
	it('skips excluded items', () => {
		expect(
			sumIncluded([
				{ amount_krw: '10000.00', is_excluded: false },
				{ amount_krw: '5000.00', is_excluded: true }
			])
		).toBe(10000);
	});

	it('returns 0 for an empty list', () => {
		expect(sumIncluded([])).toBe(0);
	});
});

describe('EXPENSE_STATUS_LABELS', () => {
	it('covers every status the API can return', () => {
		expect(Object.keys(EXPENSE_STATUS_LABELS).sort()).toEqual([
			'APPROVED',
			'DRAFT',
			'REJECTED',
			'SUBMITTED'
		]);
	});
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd frontend && npm test`
Expected: FAIL — `Failed to resolve import "./query"` / `"./expenses"`

- [ ] **Step 3: 순수 모듈을 구현한다**

`frontend/src/lib/api/query.ts`:

```ts
/**
 * 목록 API의 쿼리스트링 빌더. 배열은 반복 파라미터로 펴고(`?status=A&status=B`),
 * undefined·null·빈 문자열은 버린다. `false`는 버리지 않는다 — 불린 필터를 명시적으로
 * 끄는 요청과 "안 보냄"은 다르다.
 */
export function toQueryString(query: Record<string, unknown>): string {
	const params = new URLSearchParams();
	for (const [key, value] of Object.entries(query)) {
		if (value === undefined || value === null || value === '') continue;
		if (Array.isArray(value)) value.forEach((item) => params.append(key, String(item)));
		else params.set(key, String(value));
	}
	const search = params.toString();
	return search ? `?${search}` : '';
}
```

`frontend/src/lib/api/trips.ts`의 `tripQueryString`을 위임으로 바꾼다 (기존 테스트 5건이 그대로 지켜준다):

```ts
import { toQueryString } from './query';

export function tripQueryString(query: TripQuery): string {
	return toQueryString(query as Record<string, unknown>);
}
```

`frontend/src/lib/expenses.ts`:

```ts
import type { ExpenseStatus } from '$lib/api/types';

export const EXPENSE_STATUS_LABELS: Record<ExpenseStatus, string> = {
	DRAFT: '임시저장',
	SUBMITTED: '승인대기',
	APPROVED: '승인완료',
	REJECTED: '반려'
};

/** Badge.svelte의 tone과 그대로 맞춘다. */
export const EXPENSE_STATUS_TONES: Record<
	ExpenseStatus,
	'neutral' | 'primary' | 'success' | 'danger'
> = {
	DRAFT: 'neutral',
	SUBMITTED: 'primary',
	APPROVED: 'success',
	REJECTED: 'danger'
};

export const EXPENSE_STATUS_ORDER: ExpenseStatus[] = [
	'DRAFT',
	'SUBMITTED',
	'APPROVED',
	'REJECTED'
];

/**
 * FC/CC 상속 규칙(spec 5.5)의 화면 표현. 항목 값이 없으면 리포트 값을 쓰고, 그 사실을
 * `inherited`로 알려 "상속" 배지를 붙일 수 있게 한다. 백엔드도 같은 규칙을
 * `effective_*_code`로 내려주므로 두 값이 어긋나면 둘 중 하나가 틀린 것이다.
 */
export function resolveCenter(
	itemCode: string | null,
	reportCode: string | null
): { code: string | null; inherited: boolean } {
	if (itemCode !== null) return { code: itemCode, inherited: false };
	return { code: reportCode, inherited: true };
}

/** 금액은 API가 Decimal을 문자열로 보낸다 ("450000.00"). */
export function sumIncluded(items: { amount_krw: string; is_excluded: boolean }[]): number {
	return items
		.filter((item) => !item.is_excluded)
		.reduce((total, item) => total + Number(item.amount_krw), 0);
}
```

- [ ] **Step 4: 타입을 추가한다**

`frontend/src/lib/api/types.ts` 끝에 추가:

```ts
export type ExpenseStatus = 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED';

export interface CardItem {
	id: number;
	card_no_masked: string;
	brand: string;
	is_active: boolean;
}

export interface CardTransactionItem {
	id: number;
	card_id: number;
	approved_at: string;
	merchant_name: string;
	merchant_category_code: string;
	amount: string;
	currency_code: string;
	amount_krw: string;
	is_cancelled: boolean;
}

export interface ExpenseItem {
	id: number;
	card_transaction_id: number | null;
	expense_category_code: string;
	amount_krw: string;
	memo: string | null;
	is_excluded: boolean;
	/** null이면 리포트 값 상속 */
	fund_center_code: string | null;
	cost_center_code: string | null;
	effective_fund_center_code: string | null;
	effective_cost_center_code: string | null;
	merchant_name: string | null;
	approved_at: string | null;
}

export interface ExpenseReportListItem {
	id: number;
	report_no: string;
	status: ExpenseStatus;
	trip_id: number;
	trip_no: string;
	trip_title: string;
	trip_start_date: string;
	trip_end_date: string;
	user_id: number;
	user_name: string;
	approver_id: number | null;
	approver_name: string | null;
	fund_center_code: string | null;
	cost_center_code: string | null;
	total_amount_krw: string;
	submitted_at: string | null;
	approved_at: string | null;
}

export interface ExpenseReportDetail extends ExpenseReportListItem {
	reject_reason: string | null;
	created_at: string;
	updated_at: string;
	items: ExpenseItem[];
}

export interface MatchCandidate {
	transaction_id: number;
	approved_at: string;
	merchant_name: string;
	merchant_category_code: string;
	amount_krw: string;
	suggested_category_code: string;
	reasons: string[];
	already_added: boolean;
}

export interface ExpenseItemInput {
	card_transaction_id?: number | null;
	expense_category_code: string;
	amount_krw?: string;
	memo?: string | null;
	fund_center_code?: string | null;
	cost_center_code?: string | null;
}

export interface ExpenseItemPatch {
	expense_category_code?: string;
	amount_krw?: string;
	memo?: string | null;
	is_excluded?: boolean;
	fund_center_code?: string | null;
	cost_center_code?: string | null;
}
```

- [ ] **Step 5: API 클라이언트를 구현한다**

`frontend/src/lib/api/cards.ts`:

```ts
import { authRequest } from '$lib/stores/auth.svelte';
import { toQueryString } from './query';
import type { CardItem, CardTransactionItem, Page } from './types';

export interface CardTxnQuery {
	card_id?: number;
	approved_from?: string;
	approved_to?: string;
	merchant_category_code?: string;
	q?: string;
	include_cancelled?: boolean;
	page?: number;
	size?: number;
}

export function listCards(): Promise<CardItem[]> {
	return authRequest<CardItem[]>('/api/v1/cards');
}

export function listCardTransactions(
	query: CardTxnQuery = {}
): Promise<Page<CardTransactionItem>> {
	return authRequest<Page<CardTransactionItem>>(
		`/api/v1/card-transactions${toQueryString(query as Record<string, unknown>)}`
	);
}
```

`frontend/src/lib/api/expenses.ts`:

```ts
import { authRequest } from '$lib/stores/auth.svelte';
import { toQueryString } from './query';
import type {
	ExpenseItemInput,
	ExpenseItemPatch,
	ExpenseReportDetail,
	ExpenseReportListItem,
	ExpenseStatus,
	MatchCandidate,
	Page,
	TimelineEntry
} from './types';

export interface ExpenseQuery {
	scope?: 'mine' | 'approvals' | 'all';
	status?: ExpenseStatus[];
	q?: string;
	page?: number;
	size?: number;
}

export function listExpenses(query: ExpenseQuery = {}): Promise<Page<ExpenseReportListItem>> {
	return authRequest<Page<ExpenseReportListItem>>(
		`/api/v1/expenses${toQueryString(query as Record<string, unknown>)}`
	);
}

export function getExpense(id: number): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}`);
}

export function createExpense(tripId: number): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>('/api/v1/expenses', {
		method: 'POST',
		body: { trip_id: tripId }
	});
}

export function updateExpense(
	id: number,
	body: { fund_center_code?: string | null; cost_center_code?: string | null }
): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}`, { method: 'PATCH', body });
}

export function getMatchCandidates(id: number): Promise<MatchCandidate[]> {
	return authRequest<MatchCandidate[]>(`/api/v1/expenses/${id}/match-candidates`);
}

export function getExpenseTimeline(id: number): Promise<TimelineEntry[]> {
	return authRequest<TimelineEntry[]>(`/api/v1/expenses/${id}/timeline`);
}

export function addExpenseItem(
	id: number,
	body: ExpenseItemInput
): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}/items`, {
		method: 'POST',
		body
	});
}

export function updateExpenseItem(
	itemId: number,
	body: ExpenseItemPatch
): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expense-items/${itemId}`, {
		method: 'PATCH',
		body
	});
}

export function deleteExpenseItem(itemId: number): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expense-items/${itemId}`, {
		method: 'DELETE'
	});
}

export function submitExpense(id: number): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}/submit`, { method: 'POST' });
}

export function approveExpense(id: number): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}/approve`, { method: 'POST' });
}

export function rejectExpense(id: number, reason: string): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}/reject`, {
		method: 'POST',
		body: { reason }
	});
}

export function reopenExpense(id: number): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}/reopen`, { method: 'POST' });
}
```

인증이 필요한 호출은 전부 `authRequest`를 쓴다. raw `request`를 쓰면 401이 전역 처리되지 않는다.

- [ ] **Step 6: 통과와 타입체크를 확인한다**

Run: `cd frontend && npm test`
Expected: PASS (기존 45건 + 신규 9건 = 54건)

Run: `cd frontend && npm run check`
Expected: `0 errors, 0 warnings`

- [ ] **Step 7: 커밋**

```bash
git add frontend/src/lib/api/query.ts frontend/src/lib/api/query.test.ts frontend/src/lib/api/cards.ts frontend/src/lib/api/expenses.ts frontend/src/lib/api/trips.ts frontend/src/lib/api/types.ts frontend/src/lib/expenses.ts frontend/src/lib/expenses.test.ts
git commit -m "feat: add expense and card API clients with shared query builder"
```

---

## Task 17: 정산 상태 뱃지 + 카드거래 표 컴포넌트

**Files:**
- Create: `frontend/src/lib/components/ExpenseStatusBadge.svelte`, `frontend/src/lib/components/CardTransactionTable.svelte`

- [ ] **Step 1: 뱃지를 만든다**

`frontend/src/lib/components/ExpenseStatusBadge.svelte`:

```svelte
<script lang="ts">
	import Badge from '$lib/components/Badge.svelte';
	import { EXPENSE_STATUS_LABELS, EXPENSE_STATUS_TONES } from '$lib/expenses';
	import type { ExpenseStatus } from '$lib/api/types';

	let { status }: { status: ExpenseStatus } = $props();
</script>

<Badge tone={EXPENSE_STATUS_TONES[status]}>{EXPENSE_STATUS_LABELS[status]}</Badge>
```

- [ ] **Step 2: 카드거래 표를 만든다**

`frontend/src/lib/components/CardTransactionTable.svelte`:

```svelte
<script lang="ts">
	import type { CardTransactionItem } from '$lib/api/types';
	import { formatDateTime, formatKrw } from '$lib/format';

	let { rows }: { rows: CardTransactionItem[] } = $props();

	const CATEGORY_LABELS: Record<string, string> = {
		MEAL: '음식점',
		TRANSPORT: '교통',
		LODGING: '숙박',
		ENTERTAIN: '유흥/접대',
		ETC: '기타'
	};
</script>

<table class="w-full border-collapse">
	<thead>
		<tr class="border-b border-hairline text-left">
			<th class="py-3 text-caption text-muted">승인일시</th>
			<th class="py-3 text-caption text-muted">가맹점</th>
			<th class="py-3 text-caption text-muted">업종</th>
			<th class="py-3 text-right text-caption text-muted">금액</th>
		</tr>
	</thead>
	<tbody>
		{#each rows as row (row.id)}
			<tr class="border-b border-hairline">
				<td class="py-3 text-body-sm text-muted">{formatDateTime(row.approved_at)}</td>
				<td class="py-3 text-body-md text-ink">
					{row.merchant_name}
					{#if row.is_cancelled}
						<span class="ml-2 text-caption-sm text-error">취소</span>
					{/if}
				</td>
				<td class="py-3 text-body-sm text-muted">
					{CATEGORY_LABELS[row.merchant_category_code] ?? row.merchant_category_code}
				</td>
				<td class="py-3 text-right text-body-md text-ink">{formatKrw(row.amount_krw)}</td>
			</tr>
		{/each}
	</tbody>
</table>
```

`text-body` 클래스를 쓰지 않는다 — Tailwind가 `--color-body` 때문에 색상 유틸리티로 만들어 조용히 틀린다. `text-body-md` / `text-body-sm`을 명시한다.

- [ ] **Step 3: 타입체크**

Run: `cd frontend && npm run check`
Expected: `0 errors, 0 warnings`

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/lib/components/ExpenseStatusBadge.svelte frontend/src/lib/components/CardTransactionTable.svelte
git commit -m "feat: add expense status badge and card transaction table"
```

---

## Task 18: `/cards` 화면

**Files:**
- Create: `frontend/src/routes/cards/+page.svelte`
- Modify: `frontend/src/lib/components/AppShell.svelte`

- [ ] **Step 1: 화면을 만든다**

`frontend/src/routes/cards/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api/client';
	import { listCardTransactions, listCards } from '$lib/api/cards';
	import type { CardItem, CardTransactionItem, Page } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import CardTransactionTable from '$lib/components/CardTransactionTable.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	const SIZE = 20;

	let cards = $state<CardItem[]>([]);
	let selectedCardId = $state<number | null>(null);
	let result = $state<Page<CardTransactionItem> | null>(null);
	let currentPage = $state(1);
	let q = $state('');
	let approvedFrom = $state('');
	let approvedTo = $state('');
	let includeCancelled = $state(false);
	let loading = $state(true);
	let errorMessage = $state('');

	const totalPages = $derived(result ? Math.max(1, Math.ceil(result.total / SIZE)) : 1);

	onMount(async () => {
		try {
			cards = await listCards();
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '카드를 불러오지 못했습니다';
		}
		await load();
	});

	async function load(): Promise<void> {
		loading = true;
		errorMessage = '';
		try {
			result = await listCardTransactions({
				card_id: selectedCardId ?? undefined,
				q: q || undefined,
				approved_from: approvedFrom || undefined,
				approved_to: approvedTo || undefined,
				include_cancelled: includeCancelled,
				page: currentPage,
				size: SIZE
			});
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '거래를 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	function applyFilters(): void {
		currentPage = 1;
		void load();
	}

	function selectCard(cardId: number | null): void {
		selectedCardId = cardId;
		applyFilters();
	}

	function goToPage(next: number): void {
		currentPage = next;
		void load();
	}
</script>

<div class="flex items-center justify-between">
	<h1 class="text-display-xl">내 법인카드</h1>
	<!-- 전체 새로고침(window.location)을 쓰지 않는다 — 인증 스토어가 restore를 다시 돌아야 한다. -->
	<Button variant="secondary" onclick={() => goto('/expenses')}>정산 목록</Button>
</div>

<div class="mt-6 flex flex-wrap gap-3">
	<button
		class="rounded-full border px-4 py-2 text-button-sm {selectedCardId === null
			? 'border-ink text-ink'
			: 'border-hairline text-muted'}"
		onclick={() => selectCard(null)}
	>
		전체
	</button>
	{#each cards as card (card.id)}
		<button
			class="rounded-full border px-4 py-2 text-button-sm {selectedCardId === card.id
				? 'border-ink text-ink'
				: 'border-hairline text-muted'}"
			onclick={() => selectCard(card.id)}
		>
			{card.brand} · {card.card_no_masked}
		</button>
	{/each}
</div>

<Card>
	<div class="grid grid-cols-1 gap-4 md:grid-cols-4">
		<TextInput label="가맹점 검색" bind:value={q} placeholder="한밭식당" />
		<TextInput label="승인일 시작" type="date" bind:value={approvedFrom} />
		<TextInput label="승인일 종료" type="date" bind:value={approvedTo} />
		<div class="flex items-end gap-4">
			<label class="flex items-center gap-2 text-body-sm text-ink">
				<input type="checkbox" bind:checked={includeCancelled} class="h-4 w-4" />
				취소 포함
			</label>
			<Button onclick={applyFilters}>검색</Button>
		</div>
	</div>
</Card>

{#if errorMessage}
	<p class="mt-8 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if result && result.items.length > 0}
	<p class="mt-8 text-body-sm text-muted">전체 {result.total}건</p>
	<div class="mt-4">
		<CardTransactionTable rows={result.items} />
	</div>
	{#if totalPages > 1}
		<div class="mt-8 flex items-center justify-center gap-4">
			<Button variant="secondary" disabled={currentPage <= 1} onclick={() => goToPage(currentPage - 1)}>
				이전
			</Button>
			<span class="text-body-sm text-muted">{currentPage} / {totalPages}</span>
			<Button
				variant="secondary"
				disabled={currentPage >= totalPages}
				onclick={() => goToPage(currentPage + 1)}
			>
				다음
			</Button>
		</div>
	{/if}
{:else}
	<div class="mt-8">
		<EmptyState title="카드 거래가 없습니다" description="조건을 바꿔 다시 검색해 보세요." />
	</div>
{/if}
```

- [ ] **Step 2: 앱 셸에 링크를 단다**

`frontend/src/lib/components/AppShell.svelte`의 우측 블록에서 결재함 링크 **앞에** 추가한다 (가운데 3-탭은 DESIGN.md 규칙이라 늘리지 않는다):

```svelte
				<a
					href="/cards"
					aria-current={isActive('/cards') ? 'page' : undefined}
					class="text-button-sm {isActive('/cards') ? 'text-ink' : 'text-muted hover:text-ink'}"
				>
					카드
				</a>
```

- [ ] **Step 3: 타입체크**

Run: `cd frontend && npm run check`
Expected: `0 errors, 0 warnings`

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/routes/cards/+page.svelte frontend/src/lib/components/AppShell.svelte
git commit -m "feat: add corporate card transaction screen"
```

---

## Task 19: `/expenses` 정산 목록 화면

**Files:**
- Create: `frontend/src/routes/expenses/+page.svelte`

- [ ] **Step 1: 화면을 만든다**

`frontend/src/routes/expenses/+page.svelte`:

```svelte
<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ApiError } from '$lib/api/client';
	import { listExpenses, type ExpenseQuery } from '$lib/api/expenses';
	import type { ExpenseReportListItem, ExpenseStatus, Page } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ExpenseStatusBadge from '$lib/components/ExpenseStatusBadge.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';
	import { EXPENSE_STATUS_LABELS, EXPENSE_STATUS_ORDER } from '$lib/expenses';
	import { formatDateRange, formatKrw } from '$lib/format';
	import { auth } from '$lib/stores/auth.svelte';

	const SIZE = 12;

	let result = $state<Page<ExpenseReportListItem> | null>(null);
	let loading = $state(true);
	let errorMessage = $state('');

	let q = $state(page.url.searchParams.get('q') ?? '');
	let status = $state<ExpenseStatus | ''>(
		(page.url.searchParams.get('status') as ExpenseStatus) ?? ''
	);
	let scope = $state<'mine' | 'approvals'>(
		page.url.searchParams.get('scope') === 'approvals' ? 'approvals' : 'mine'
	);

	const canApprove = $derived(auth.user?.role === 'MANAGER' || auth.user?.role === 'ADMIN');
	const currentPage = $derived(Number(page.url.searchParams.get('page') ?? '1'));
	const totalPages = $derived(result ? Math.max(1, Math.ceil(result.total / SIZE)) : 1);

	const statusOptions = EXPENSE_STATUS_ORDER.map((value) => ({
		value,
		label: EXPENSE_STATUS_LABELS[value]
	}));

	// page.url.search만 의존성으로 읽는다 — 아래에서 대입하는 상태는 이 effect가 읽지
	// 않으므로 다시 트리거되지 않는다.
	$effect(() => {
		const search = page.url.search;
		void load(new URLSearchParams(search));
	});

	async function load(params: URLSearchParams): Promise<void> {
		loading = true;
		errorMessage = '';
		const query: ExpenseQuery = { page: Number(params.get('page') ?? '1'), size: SIZE };
		const searchText = params.get('q');
		const statusValue = params.get('status');
		if (searchText) query.q = searchText;
		if (statusValue) query.status = [statusValue as ExpenseStatus];
		if (params.get('scope') === 'approvals') query.scope = 'approvals';
		try {
			result = await listExpenses(query);
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '정산 목록을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	function applyFilters(): void {
		const params = new URLSearchParams();
		if (q) params.set('q', q);
		if (status) params.set('status', status);
		if (scope === 'approvals') params.set('scope', 'approvals');
		goto(`/expenses${params.toString() ? `?${params}` : ''}`);
	}

	function goToPage(next: number): void {
		const params = new URLSearchParams(page.url.searchParams);
		params.set('page', String(next));
		goto(`/expenses?${params}`);
	}
</script>

<div class="flex items-center justify-between">
	<h1 class="text-display-xl">정산</h1>
	<Button variant="secondary" onclick={() => goto('/cards')}>카드 내역</Button>
</div>

<Card>
	<div class="grid grid-cols-1 gap-4 md:grid-cols-4">
		<TextInput label="검색" bind:value={q} placeholder="정산번호 · 출장명" />
		<Select label="상태" bind:value={status} options={statusOptions} placeholder="전체" />
		{#if canApprove}
			<Select
				label="구분"
				bind:value={scope}
				options={[
					{ value: 'mine', label: '내 정산' },
					{ value: 'approvals', label: '결재 대상' }
				]}
				placeholder="내 정산"
			/>
		{/if}
		<div class="flex items-end">
			<Button onclick={applyFilters}>검색</Button>
		</div>
	</div>
</Card>

{#if errorMessage}
	<p class="mt-8 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if result && result.items.length > 0}
	<p class="mt-8 text-body-sm text-muted">전체 {result.total}건</p>
	<div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
		{#each result.items as report (report.id)}
			<a href={`/expenses/${report.id}`} class="block">
				<Card hoverable>
					<div class="flex items-start justify-between">
						<p class="text-caption text-muted">{report.report_no}</p>
						<ExpenseStatusBadge status={report.status} />
					</div>
					<p class="mt-2 text-title-md text-ink">{report.trip_title}</p>
					<p class="mt-1 text-body-sm text-muted">
						{report.trip_no} · {formatDateRange(report.trip_start_date, report.trip_end_date)}
					</p>
					<p class="mt-4 text-display-sm text-ink">{formatKrw(report.total_amount_krw)}</p>
					<p class="mt-2 text-caption-sm text-muted">
						{report.user_name} → {report.approver_name ?? '결재자 미지정'}
					</p>
				</Card>
			</a>
		{/each}
	</div>

	{#if totalPages > 1}
		<div class="mt-8 flex items-center justify-center gap-4">
			<Button variant="secondary" disabled={currentPage <= 1} onclick={() => goToPage(currentPage - 1)}>
				이전
			</Button>
			<span class="text-body-sm text-muted">{currentPage} / {totalPages}</span>
			<Button
				variant="secondary"
				disabled={currentPage >= totalPages}
				onclick={() => goToPage(currentPage + 1)}
			>
				다음
			</Button>
		</div>
	{/if}
{:else}
	<div class="mt-8">
		<EmptyState
			title="정산서가 없습니다"
			description="완료된 출장 상세에서 정산서를 만들 수 있습니다."
		>
			{#snippet action()}
				<Button onclick={() => goto('/trips?status=COMPLETED')}>완료된 출장 보기</Button>
			{/snippet}
		</EmptyState>
	</div>
{/if}
```

- [ ] **Step 2: 타입체크**

Run: `cd frontend && npm run check`
Expected: `0 errors, 0 warnings`

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/routes/expenses/+page.svelte
git commit -m "feat: add expense report list screen"
```

---

## Task 20: 자동매칭 패널 + 항목 테이블 컴포넌트

**Files:**
- Create: `frontend/src/lib/components/MatchPanel.svelte`, `frontend/src/lib/components/ExpenseItemsTable.svelte`

- [ ] **Step 1: 매칭 패널을 만든다**

`frontend/src/lib/components/MatchPanel.svelte`:

```svelte
<script lang="ts">
	import type { MatchCandidate } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import { formatDateTime, formatKrw } from '$lib/format';

	let {
		candidates,
		busy = false,
		editable = true,
		onadd
	}: {
		candidates: MatchCandidate[];
		busy?: boolean;
		editable?: boolean;
		onadd: (candidate: MatchCandidate) => void;
	} = $props();
</script>

{#if candidates.length === 0}
	<p class="text-body-sm text-muted">출장 기간과 겹치는 카드 거래가 없습니다.</p>
{:else}
	<ul class="flex flex-col gap-3">
		{#each candidates as candidate (candidate.transaction_id)}
			<li class="flex items-start justify-between gap-4 rounded-md border border-hairline px-4 py-3">
				<div>
					<p class="text-title-sm text-ink">{candidate.merchant_name}</p>
					<p class="mt-1 text-caption-sm text-muted">{formatDateTime(candidate.approved_at)}</p>
					<div class="mt-2 flex flex-wrap gap-2">
						{#each candidate.reasons as reason (reason)}
							<!-- 매칭 사유는 API가 준 문자열을 그대로 쓴다. 화면에서 따로 만들면
							     Agent가 받는 설명과 사람이 보는 설명이 갈라진다. -->
							<span class="rounded-full bg-surface-soft px-2.5 py-1 text-badge text-ink">
								{reason}
							</span>
						{/each}
					</div>
				</div>
				<div class="flex shrink-0 flex-col items-end gap-2">
					<p class="text-body-md text-ink">{formatKrw(candidate.amount_krw)}</p>
					{#if candidate.already_added}
						<span class="text-caption-sm text-muted">담김</span>
					{:else if editable}
						<Button variant="pill" disabled={busy} onclick={() => onadd(candidate)}>담기</Button>
					{/if}
				</div>
			</li>
		{/each}
	</ul>
{/if}
```

- [ ] **Step 2: 항목 테이블을 만든다**

`frontend/src/lib/components/ExpenseItemsTable.svelte`:

```svelte
<script lang="ts">
	import type { ExpenseItem, ExpenseItemPatch, ExpenseReportDetail } from '$lib/api/types';
	import { formatKrw } from '$lib/format';
	import { resolveCenter } from '$lib/expenses';

	let {
		report,
		categories,
		costCenters,
		fundCenters,
		editable = true,
		busy = false,
		onupdate,
		ondelete
	}: {
		report: ExpenseReportDetail;
		categories: { value: string; label: string }[];
		costCenters: { value: string; label: string }[];
		fundCenters: { value: string; label: string }[];
		editable?: boolean;
		busy?: boolean;
		onupdate: (itemId: number, patch: ExpenseItemPatch) => void;
		ondelete: (itemId: number) => void;
	} = $props();

	// 행 안의 셀렉트는 Select.svelte 대신 raw <select>를 쓴다 — 표에서는 라벨 텍스트가
	// 열 머리글로 이미 있고, 행마다 시각적 라벨을 반복하면 표가 읽히지 않는다.
	// 접근성은 aria-label로 채운다.
	function centerLabel(item: ExpenseItem): string {
		const { code, inherited } = resolveCenter(item.cost_center_code, report.cost_center_code);
		if (code === null) return '미지정';
		return inherited ? `${code} (상속)` : code;
	}
</script>

<table class="w-full border-collapse">
	<thead>
		<tr class="border-b border-hairline text-left">
			<th class="py-3 text-caption text-muted">가맹점 / 메모</th>
			<th class="py-3 text-caption text-muted">비목</th>
			<th class="py-3 text-caption text-muted">코스트센터</th>
			<th class="py-3 text-caption text-muted">펀드센터</th>
			<th class="py-3 text-right text-caption text-muted">금액</th>
			<th class="py-3 text-right text-caption text-muted">제외</th>
			<th class="py-3"></th>
		</tr>
	</thead>
	<tbody>
		{#each report.items as item (item.id)}
			<tr class="border-b border-hairline {item.is_excluded ? 'text-muted-soft' : ''}">
				<td class="py-3 text-body-md text-ink">
					{item.merchant_name ?? '수기 항목'}
					{#if item.memo}
						<span class="ml-2 text-caption-sm text-muted">{item.memo}</span>
					{/if}
				</td>
				<td class="py-3">
					{#if editable}
						<select
							aria-label="비목"
							value={item.expense_category_code}
							disabled={busy}
							onchange={(event) =>
								onupdate(item.id, {
									expense_category_code: (event.currentTarget as HTMLSelectElement).value
								})}
							class="h-10 rounded-sm border border-hairline bg-canvas px-2 text-body-sm text-ink"
						>
							{#each categories as option (option.value)}
								<option value={option.value}>{option.label}</option>
							{/each}
						</select>
					{:else}
						<span class="text-body-sm text-ink">{item.expense_category_code}</span>
					{/if}
				</td>
				<td class="py-3">
					{#if editable}
						<select
							aria-label="코스트센터"
							value={item.cost_center_code ?? ''}
							disabled={busy}
							onchange={(event) =>
								onupdate(item.id, {
									cost_center_code:
										(event.currentTarget as HTMLSelectElement).value || null
								})}
							class="h-10 rounded-sm border border-hairline bg-canvas px-2 text-body-sm text-ink"
						>
							<option value="">상속 ({report.cost_center_code ?? '미지정'})</option>
							{#each costCenters as option (option.value)}
								<option value={option.value}>{option.label}</option>
							{/each}
						</select>
					{:else}
						<span class="text-body-sm text-ink">{centerLabel(item)}</span>
					{/if}
				</td>
				<td class="py-3">
					{#if editable}
						<select
							aria-label="펀드센터"
							value={item.fund_center_code ?? ''}
							disabled={busy}
							onchange={(event) =>
								onupdate(item.id, {
									fund_center_code:
										(event.currentTarget as HTMLSelectElement).value || null
								})}
							class="h-10 rounded-sm border border-hairline bg-canvas px-2 text-body-sm text-ink"
						>
							<option value="">상속 ({report.fund_center_code ?? '미지정'})</option>
							{#each fundCenters as option (option.value)}
								<option value={option.value}>{option.label}</option>
							{/each}
						</select>
					{:else}
						<span class="text-body-sm text-ink">
							{item.effective_fund_center_code ?? '미지정'}
						</span>
					{/if}
				</td>
				<td class="py-3 text-right text-body-md text-ink">{formatKrw(item.amount_krw)}</td>
				<td class="py-3 text-right">
					<input
						type="checkbox"
						aria-label="정산에서 제외"
						checked={item.is_excluded}
						disabled={!editable || busy}
						onchange={(event) =>
							onupdate(item.id, {
								is_excluded: (event.currentTarget as HTMLInputElement).checked
							})}
						class="h-4 w-4"
					/>
				</td>
				<td class="py-3 text-right">
					{#if editable}
						<button
							class="text-button-sm text-ink underline-offset-4 hover:underline disabled:text-muted-soft"
							disabled={busy}
							onclick={() => ondelete(item.id)}
						>
							삭제
						</button>
					{/if}
				</td>
			</tr>
		{/each}
	</tbody>
</table>
```

- [ ] **Step 3: 타입체크**

Run: `cd frontend && npm run check`
Expected: `0 errors, 0 warnings`

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/lib/components/MatchPanel.svelte frontend/src/lib/components/ExpenseItemsTable.svelte
git commit -m "feat: add match panel and expense items table components"
```

---

## Task 21: `/expenses/[id]` 정산서 작성 화면

DESIGN.md 매핑: 우측 sticky 액션 카드는 `reservation-card`, 총액은 `rating-display`(64px = `text-display-xl`)로 표현한다 — 시스템에서 유일하게 큰 타이포 순간이다.

**Files:**
- Create: `frontend/src/routes/expenses/[id]/+page.svelte`

- [ ] **Step 1: 화면을 만든다**

`frontend/src/routes/expenses/[id]/+page.svelte`:

```svelte
<script lang="ts">
	import { page } from '$app/state';
	import { ApiError } from '$lib/api/client';
	import { listCostCenters, listFundCenters } from '$lib/api/centers';
	import { byGroupCode, listCodeGroups } from '$lib/api/codes';
	import {
		addExpenseItem,
		approveExpense,
		deleteExpenseItem,
		getExpense,
		getExpenseTimeline,
		getMatchCandidates,
		rejectExpense,
		reopenExpense,
		submitExpense,
		updateExpense,
		updateExpenseItem
	} from '$lib/api/expenses';
	import type {
		ExpenseItemPatch,
		ExpenseReportDetail,
		MatchCandidate,
		TimelineEntry
	} from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import ExpenseItemsTable from '$lib/components/ExpenseItemsTable.svelte';
	import ExpenseStatusBadge from '$lib/components/ExpenseStatusBadge.svelte';
	import MatchPanel from '$lib/components/MatchPanel.svelte';
	import Select from '$lib/components/Select.svelte';
	import Textarea from '$lib/components/Textarea.svelte';
	import Timeline from '$lib/components/Timeline.svelte';
	import { formatDateRange, formatKrw } from '$lib/format';
	import { auth } from '$lib/stores/auth.svelte';

	let report = $state<ExpenseReportDetail | null>(null);
	let candidates = $state<MatchCandidate[]>([]);
	let entries = $state<TimelineEntry[]>([]);
	let categories = $state<{ value: string; label: string }[]>([]);
	let costCenters = $state<{ value: string; label: string }[]>([]);
	let fundCenters = $state<{ value: string; label: string }[]>([]);
	let loading = $state(true);
	let errorMessage = $state('');
	let actionError = $state('');
	let busy = $state(false);
	let rejecting = $state(false);
	let rejectReason = $state('');
	let fundCenterValue = $state('');
	let costCenterValue = $state('');

	const reportId = $derived(Number(page.params.id));
	const isOwner = $derived(!!report && report.user_id === auth.user?.id);
	const isApprover = $derived(!!report && report.approver_id === auth.user?.id);
	const editable = $derived(
		!!report && isOwner && (report.status === 'DRAFT' || report.status === 'REJECTED')
	);

	$effect(() => {
		const id = reportId;
		void load(id);
	});

	// 서버 값이 바뀌면 헤더 셀렉트를 맞춘다. PATCH 응답이 곧 진실이므로 사용자의 선택이
	// 응답으로 덮이는 것은 의도된 동작이다.
	$effect(() => {
		fundCenterValue = report?.fund_center_code ?? '';
		costCenterValue = report?.cost_center_code ?? '';
	});

	async function load(id: number): Promise<void> {
		loading = true;
		errorMessage = '';
		try {
			const [detail, matched, timeline, groups, costs, funds] = await Promise.all([
				getExpense(id),
				getMatchCandidates(id),
				getExpenseTimeline(id),
				listCodeGroups(),
				listCostCenters(),
				listFundCenters()
			]);
			report = detail;
			candidates = matched;
			entries = timeline;
			categories = (byGroupCode(groups).EXPENSE_CATEGORY?.codes ?? []).map((code) => ({
				value: code.code,
				label: code.name
			}));
			costCenters = costs.map((center) => ({
				value: center.code,
				label: `${center.code} · ${center.name}`
			}));
			fundCenters = funds.map((center) => ({
				value: center.code,
				label: `${center.code} · ${center.name}`
			}));
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '정산서를 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	/**
	 * 모든 쓰기는 이 한 곳을 지난다. 첫 줄의 `if (busy) return;`이 중복 제출 가드다 —
	 * 버튼의 disabled만으로는 연타·엔터 경로를 막지 못하고, 항목 추가와 제출은 멱등하지
	 * 않아 중복 호출이 곧 중복 레코드다.
	 */
	async function act(
		action: () => Promise<ExpenseReportDetail>,
		{ refreshCandidates = false }: { refreshCandidates?: boolean } = {}
	): Promise<void> {
		if (busy) return;
		busy = true;
		actionError = '';
		try {
			report = await action();
			entries = await getExpenseTimeline(reportId);
			if (refreshCandidates) candidates = await getMatchCandidates(reportId);
			rejecting = false;
			rejectReason = '';
		} catch (error) {
			actionError = error instanceof ApiError ? error.message : '처리하지 못했습니다';
		} finally {
			busy = false;
		}
	}

	function addCandidate(candidate: MatchCandidate): void {
		void act(
			() =>
				addExpenseItem(reportId, {
					card_transaction_id: candidate.transaction_id,
					expense_category_code: candidate.suggested_category_code
				}),
			{ refreshCandidates: true }
		);
	}

	function patchItem(itemId: number, patch: ExpenseItemPatch): void {
		void act(() => updateExpenseItem(itemId, patch));
	}

	function removeItem(itemId: number): void {
		void act(() => deleteExpenseItem(itemId), { refreshCandidates: true });
	}

	/**
	 * 셀렉트 변경마다 PATCH를 보내지 않고 명시적 저장 버튼을 둔다. 두 값을 연달아 고칠 때
	 * 왕복이 두 번 생기고, 늦게 도착한 응답이 방금 고른 값을 덮을 수 있기 때문이다.
	 */
	function saveCenters(): void {
		void act(() =>
			updateExpense(reportId, {
				fund_center_code: fundCenterValue || null,
				cost_center_code: costCenterValue || null
			})
		);
	}
</script>

{#if loading}
	<p class="text-body-sm text-muted">불러오는 중…</p>
{:else if errorMessage}
	<p class="text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if report}
	<div class="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
		<div>
			<p class="text-caption text-muted">{report.report_no}</p>
			<div class="mt-2 flex items-center gap-3">
				<h1 class="text-display-xl">{report.trip_title}</h1>
				<ExpenseStatusBadge status={report.status} />
			</div>
			<p class="mt-2 text-body-sm text-muted">
				<a href={`/trips/${report.trip_id}`} class="underline-offset-4 hover:underline">
					{report.trip_no}
				</a>
				· {formatDateRange(report.trip_start_date, report.trip_end_date)}
			</p>

			{#if report.status === 'REJECTED' && report.reject_reason}
				<div class="mt-6 rounded-md border border-error px-4 py-3">
					<p class="text-caption text-error">반려 사유</p>
					<p class="mt-1 text-body-md text-ink">{report.reject_reason}</p>
				</div>
			{/if}

			<h2 class="mt-10 text-display-sm">비용 처리 부서</h2>
			<div class="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2">
				<Select
					label="펀드센터 (기본값)"
					bind:value={fundCenterValue}
					options={fundCenters}
					disabled={!editable || busy}
				/>
				<Select
					label="코스트센터 (기본값)"
					bind:value={costCenterValue}
					options={costCenters}
					disabled={!editable || busy}
				/>
			</div>
			{#if editable}
				<div class="mt-4">
					<Button variant="secondary" disabled={busy} onclick={saveCenters}>부서 저장</Button>
				</div>
			{/if}

			<h2 class="mt-10 text-display-sm">자동매칭 후보</h2>
			<p class="mt-1 text-body-sm text-muted">
				출장 기간 전후 1일 이내의 본인 법인카드 사용내역입니다.
			</p>
			<div class="mt-4">
				<MatchPanel {candidates} {busy} editable={editable} onadd={addCandidate} />
			</div>

			<h2 class="mt-10 text-display-sm">정산 항목</h2>
			<div class="mt-4">
				{#if report.items.length === 0}
					<p class="text-body-sm text-muted">아직 담은 항목이 없습니다.</p>
				{:else}
					<ExpenseItemsTable
						{report}
						{categories}
						{costCenters}
						{fundCenters}
						{editable}
						{busy}
						onupdate={patchItem}
						ondelete={removeItem}
					/>
				{/if}
			</div>

			<h2 class="mt-10 text-display-sm">진행 이력</h2>
			<div class="mt-4">
				<Timeline {entries} />
			</div>
		</div>

		<aside class="lg:sticky lg:top-8 lg:self-start">
			<Card>
				<p class="text-caption text-muted">정산 총액</p>
				<p class="mt-1 text-display-xl text-ink">{formatKrw(report.total_amount_krw)}</p>
				<p class="mt-2 text-caption-sm text-muted">
					{report.user_name} → {report.approver_name ?? '결재자 미지정'}
				</p>

				{#if actionError}
					<p class="mt-4 text-caption-sm text-error" role="alert">{actionError}</p>
				{/if}

				<div class="mt-6 flex flex-col gap-3">
					{#if isOwner && report.status === 'DRAFT'}
						<Button full disabled={busy} onclick={() => act(() => submitExpense(reportId))}>
							제출
						</Button>
					{/if}

					{#if isOwner && report.status === 'REJECTED'}
						<Button
							full
							variant="secondary"
							disabled={busy}
							onclick={() => act(() => reopenExpense(reportId))}
						>
							다시 작성
						</Button>
					{/if}

					{#if isApprover && report.status === 'SUBMITTED'}
						<Button full disabled={busy} onclick={() => act(() => approveExpense(reportId))}>
							승인
						</Button>
						{#if rejecting}
							<Textarea label="반려 사유" bind:value={rejectReason} rows={3} />
							<Button
								full
								variant="secondary"
								disabled={busy}
								onclick={() => act(() => rejectExpense(reportId, rejectReason))}
							>
								반려 확정
							</Button>
							<Button full variant="tertiary" disabled={busy} onclick={() => (rejecting = false)}>
								취소
							</Button>
						{:else}
							<Button full variant="secondary" disabled={busy} onclick={() => (rejecting = true)}>
								반려
							</Button>
						{/if}
					{/if}

					{#if report.status === 'APPROVED'}
						<p class="text-body-sm text-muted">승인 완료 — 출장이 정산완료로 전이되었습니다.</p>
					{/if}
				</div>
			</Card>
		</aside>
	</div>
{/if}
```

- [ ] **Step 2: 타입체크**

Run: `cd frontend && npm run check`
Expected: `0 errors, 0 warnings`

`Select.svelte`는 `onchange` prop이 없고 `bind:value`만 지원한다 — 위 코드가 그 계약을 따르는지 확인한다. `$props.id()`는 `Select.svelte` 안에서 컴포넌트당 한 번만 불리므로 이 화면에서 셀렉트를 두 개 쓰는 것은 문제가 없다.

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/routes/expenses/[id]/+page.svelte
git commit -m "feat: add expense report detail screen with matching and approval"
```

---

## Task 22: 출장 상세 · 대시보드에서 정산으로 잇기

**Files:**
- Modify: `frontend/src/routes/trips/[id]/+page.svelte:210-212`, `frontend/src/routes/+page.svelte:75-81`

- [ ] **Step 1: 출장 상세의 자리표시자를 실제 동작으로 바꾼다**

`frontend/src/routes/trips/[id]/+page.svelte`의 `<script>`에 추가:

```ts
	import { createExpense, listExpenses } from '$lib/api/expenses';

	let reportId = $state<number | null>(null);

	// 출장 상세에서 정산서 존재 여부를 알려면 목록을 한 번 봐야 한다. 전용
	// GET /trips/{id}/expense 엔드포인트를 만들지 않은 것은 목록 필터로 충분하기 때문이다.
	async function loadReport(id: number): Promise<void> {
		try {
			const page = await listExpenses({ size: 100 });
			reportId = page.items.find((item) => item.trip_id === id)?.id ?? null;
		} catch {
			reportId = null;
		}
	}

	async function startExpense(): Promise<void> {
		if (busy) return;
		busy = true;
		actionError = '';
		try {
			const created = await createExpense(tripId);
			await goto(`/expenses/${created.id}`);
		} catch (error) {
			actionError = error instanceof ApiError ? error.message : '정산서를 만들지 못했습니다';
			busy = false;
		}
	}
```

기존 `load` 함수의 `Promise.all` 뒤에 `void loadReport(id);` 한 줄을 더한다.

마크업의 `{#if trip.status === 'COMPLETED' || trip.status === 'SETTLED'}` 블록을 아래로 교체한다:

```svelte
					{#if isOwner && (trip.status === 'APPROVED' || trip.status === 'COMPLETED' || trip.status === 'SETTLED')}
						{#if reportId !== null}
							<Button
								full
								variant="secondary"
								disabled={busy}
								onclick={() => goto(`/expenses/${reportId}`)}
							>
								정산서 보기
							</Button>
						{:else}
							<Button full variant="secondary" disabled={busy} onclick={startExpense}>
								정산서 작성
							</Button>
						{/if}
					{/if}
```

- [ ] **Step 2: 대시보드의 "정산은 Phase 3" 뱃지를 없앤다**

`frontend/src/routes/+page.svelte`의 미정산 카드를 아래로 바꾼다:

```svelte
	<a href="/expenses" class="block">
		<Card hoverable>
			<p class="text-caption text-muted">미정산 출장</p>
			<p class="mt-2 text-display-md">{loading ? '…' : `${unsettled}건`}</p>
			<div class="mt-3"><Badge>정산 진행</Badge></div>
		</Card>
	</a>
```

- [ ] **Step 3: 타입체크와 테스트**

Run: `cd frontend && npm run check && npm test`
Expected: `0 errors, 0 warnings` · 테스트 54건 PASS

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/routes/trips/[id]/+page.svelte frontend/src/routes/+page.svelte
git commit -m "feat: link trips and dashboard to the expense flow"
```

---

## Task 23: 전체 검증 (백엔드 · 프론트 · 빌드)

**Files:** 없음 (검증만)

- [ ] **Step 1: 백엔드 전체**

Run: `cd backend && uv run pytest -q`
Expected: 전부 PASS. 실패 건이 있으면 여기서 멈추고 고친다.

- [ ] **Step 2: 프론트 전체**

Run: `cd frontend && npm test && npm run check && npm run build`
Expected: 테스트 PASS · `0 errors, 0 warnings` · 빌드 성공

- [ ] **Step 3: 금지 패턴 grep**

Run:
```bash
cd frontend && grep -rn "text-body\b\|crypto.randomUUID" src | grep -v "text-body-md\|text-body-sm" | wc -l
```
Expected: `0` — `text-body`는 색상 유틸리티로 조용히 틀리고, `crypto.randomUUID`는 평문 HTTP 운영에서 페이지 전체를 죽인다.

Run:
```bash
cd frontend && grep -rn "request<" src/lib/api | grep -v authRequest | grep -v "client.ts" | wc -l
```
Expected: `0` — 인증 호출은 전부 `authRequest`를 지난다.

Run:
```bash
cd backend && grep -rn "relationship(" app/models | wc -l
```
Expected: 기존 값과 동일 (`CodeGroup.codes` 하나). 정산 모델에 relationship을 추가하지 않았는지 확인한다.

- [ ] **Step 4: 실서버 스모크 (수동)**

터미널 두 개로 백엔드·프론트를 띄운다.

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

curl로 Agent 경로를 그대로 밟는다 (`$TOKEN`은 로그인 응답의 `access_token`):

```bash
TOKEN=$(curl -s localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"user1@skon.example","password":"skon1234!"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s "localhost:8000/api/v1/trips?status=COMPLETED&size=3" -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/api/v1/expenses -X POST -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"trip_id":<위에서 고른 id>}'
curl -s "localhost:8000/api/v1/expenses/<report_id>/match-candidates" -H "Authorization: Bearer $TOKEN"
```

확인할 것: 후보에 `reasons` 문자열이 실려 오고, 그 값이 화면의 사유 배지와 **글자까지 같다**. 다르면 화면이 사유를 자체 생성하고 있는 것이다.

- [ ] **Step 5: 커밋 없음 — 검증 결과를 다음 태스크의 문서에 기록한다**

---

## Task 24: 브라우저 수동 시나리오

Phase 2에서 이월된 8개 + Phase 3 신규 6개다. 실브라우저(`localhost:5173`)에서 눌러본다. 각 항목 옆에 실제 결과를 적는다.

- [ ] **Step 1: Phase 2 이월 시나리오 (8건)**

1. 로그아웃 상태에서 `/trips/3` 직접 열기 → 로그인 후 `/trips/3`으로 복귀하는가 (딥링크 보존)
2. 출장 신청 폼에서 저장 버튼 연타 → 출장이 1건만 생기는가 (중복 제출 가드)
3. 반려된 출장 → 수정 → 다시 작성 → 재상신이 화면 흐름으로 이어지는가
4. localStorage의 토큰을 손으로 망가뜨린 뒤 아무 목록이나 열기 → 로그인 화면으로 정리되는가 (전역 401)
5. 결재자 계정으로 로그인 → 결재함 링크가 보이고 목록이 차는가
6. EMPLOYEE 계정 → 결재함 링크가 보이지 않는가
7. 알림 벨 뱃지 숫자가 알림 읽음 처리 후 줄어드는가
8. 목록 필터(검색어·상태·시작일)를 걸고 새로고침 → 필터가 URL로 살아 있는가

- [ ] **Step 2: Phase 3 신규 시나리오 (6건)**

9. `/cards`에서 카드 pill을 바꾸면 거래 목록이 그 카드로 좁혀지는가. "취소 포함"을 켜면 취소 거래가 나타나는가
10. COMPLETED 출장 상세 → "정산서 작성" → `/expenses/[id]`로 이동하고 코스트센터가 출장 값으로 승계돼 있는가
11. 자동매칭 후보의 "담기" → 항목 테이블에 추가되고 총액이 늘며, 그 후보가 "담김"으로 바뀌는가
12. 항목의 코스트센터를 "상속"에서 다른 값으로 바꾸면 표에 그 값이 남고, 다시 "상속"으로 되돌리면 헤더 값이 표시되는가
13. 펀드센터를 비운 채 "제출" → `CENTER_REQUIRED` 메시지가 액션 카드에 뜨는가
14. 결재자 계정으로 승인 → 정산서가 승인완료가 되고, 해당 출장 상세의 상태가 **정산완료**로 바뀌며 출장 타임라인에 SETTLED 항목이 생기는가

- [ ] **Step 3: 발견한 문제를 기록한다**

고칠 수 있는 것은 이 Phase에서 고치고, 넘길 것은 다음 태스크에서 `docs/phase-status.md`의 "Phase 3에서 넘어온 항목"에 적는다. 아무것도 발견하지 못했다면 그 사실을 적는다 — "확인함"과 "안 해봄"은 다르다.

- [ ] **Step 4: 커밋 (수정이 있었을 때만)**

```bash
git add -A
git commit -m "fix: address issues found in manual browser verification"
```

---

## Task 25: 문서 갱신

**Files:**
- Modify: `docs/phase-status.md`, `CLAUDE.md`, `README.md`

- [ ] **Step 1: `docs/phase-status.md`를 갱신한다**

- 상단 표에서 Phase 3을 **완료**로, Phase 4를 "다음"으로 바꾼다.
- 테스트 건수를 실제 값으로 갱신한다 (Task 23 Step 1·2의 출력).
- "Phase 3 — 정산" 절을 **완료 기록**으로 다시 쓴다: 서비스 모듈 표(`matching.py`·`expense_rules.py`·`expenses.py`·`cards.py`), API 목록, 화면 목록, 실서버 검증 결과, 설계에서 벗어난 결정 3건(`PATCH /expenses/{id}`, `reopen`, `timeline`).
- "Phase 2에서 넘어온 항목"에서 처리된 것을 지운다: `load_active_codes`, `assert_center_code`/`assert_fund_center`, `GET /fund-centers` 소비처, `COMPLETED → SETTLED`, 브라우저 시나리오 8개.
- **"Phase 3에서 넘어온 항목"** 절을 새로 쓴다. 최소한 아래를 적는다:
  - 정산서 목록의 `q` 필터도 LIKE 와일드카드를 이스케이프하지 않는다 (출장과 같은 판단).
  - `next_report_no`도 `max() + 1`이다. 멀티 레플리카 전제가 생기면 `next_trip_no`와 함께 시퀀스로 옮긴다.
  - 출장 상세가 정산서 존재 여부를 알기 위해 정산 목록을 `size=100`으로 훑는다. 데모 규모에서는 충분하나, 정산서가 100건을 넘으면 놓친다 — 전용 조회나 `trip_id` 필터가 필요하다.
  - 항목의 FC/CC override는 마스터 비활성화 시점에 재검증되지 않는다 (제출 시 헤더만 재검증한다).
  - Task 24에서 발견한 미해결 항목.
- Phase 4 착수 시 볼 것(`UNRESTRICTED` 센티널)은 그대로 남긴다.

- [ ] **Step 2: `CLAUDE.md`를 갱신한다**

- 첫 단락의 "Phase 1(기반)·Phase 2(출장) 완료. 다음은 Phase 3(정산)."을 "Phase 1~3 완료. 다음은 Phase 4(개발자)."로 바꾼다.
- 테스트 건수를 갱신한다.
- "반드시 지킬 것"에 두 줄을 추가한다:
  - **정산서 전이도 `assert_expense_transition_allowed` 하나만 통과한다.** 출장과 같은 이유이며, `EXPENSE_TRANSITION_ACTOR`에 엔트리를 빠뜨리면 임포트가 깨진다.
  - **`COMPLETED → SETTLED`는 `settle_trip_for_report`만 수행한다.** `assert_system_transition`을 지나고 `record_transition`을 남기며 commit하지 않는다 — 정산서 승인과 같은 트랜잭션이어야 한다.
- "다음 Phase로 넘어간 항목" 절을 Phase 3 기준으로 교체한다.

- [ ] **Step 3: `README.md`를 갱신한다**

화면·API 목록에 `/cards` · `/expenses` · `/expenses/[id]`와 정산 엔드포인트를 더한다.

- [ ] **Step 4: 문서가 실제 코드와 맞는지 확인한다**

Run: `cd backend && uv run python -c "from app.main import app; print(len(app.openapi()['paths']))"`
문서에 적은 엔드포인트 수와 대조한다.

- [ ] **Step 5: 커밋**

```bash
git add docs/phase-status.md CLAUDE.md README.md
git commit -m "docs: record Phase 3 completion and carry-over items"
```

---

## 완료 기준

- [ ] `cd backend && uv run pytest` 전부 통과
- [ ] `cd frontend && npm test` 전부 통과
- [ ] `cd frontend && npm run check` — 0 errors / 0 warnings
- [ ] `cd frontend && npm run build` 성공
- [ ] Task 24의 14개 시나리오를 실브라우저에서 확인하고 결과를 기록
- [ ] `docs/phase-status.md`에 Phase 3 완료와 이월 항목이 적혀 있음
- [ ] 자동매칭 사유 문자열이 API 응답과 화면에서 동일

## 자기 점검 결과 (계획 작성자 기록)

- **spec 커버리지**: spec 5.5(정산 모델·FC/CC 계층·생성 제약) → Task 5·10·11, spec 5.6(자동매칭) → Task 4·12, spec 5.4의 `COMPLETED → SETTLED` → Task 3·13·14, spec 6의 `/cards`·`/expenses`·`/expenses/[id]` → Task 18·19·21, spec 7의 정산 엔드포인트 → Task 15, spec 8의 단위/통합 테스트 분리 → Task 4·5(DB 없음) + Task 10~15(통합).
- **spec 7 목록에 있으나 이 계획이 다르게 구현하는 것**: `POST /expenses/{id}/items`가 204가 아니라 갱신된 정산서를 돌려준다(Task 15). 왕복을 줄이려는 의도이며 spec은 응답 형식을 규정하지 않았다.
- **타입 일관성 확인**: `MatchCandidate`(백엔드 dataclass)와 `MatchCandidateOut`(응답 스키마)와 `MatchCandidate`(프론트 인터페이스)는 이름이 겹치지만 계층이 다르고, 프론트가 보는 필드는 `MatchCandidateOut`과 1:1이다. `effective_*_code`는 Task 7에서 정의하고 Task 10·20에서 같은 이름으로 소비한다. `resolveCenter`(프론트)와 `effective_center`(백엔드)는 같은 규칙의 두 구현이며, 어긋나면 Task 24 시나리오 12가 잡는다.

