# Phase 현황 — 완료분과 다음 작업

- 기준: Phase 2 (출장) 완료 시점
- 설계: [`superpowers/specs/2026-08-12-skon-biztrip-web-design.md`](superpowers/specs/2026-08-12-skon-biztrip-web-design.md)
- Phase 1 계획: [`superpowers/plans/2026-08-12-phase1-foundation.md`](superpowers/plans/2026-08-12-phase1-foundation.md)
- Phase 2 계획: [`superpowers/plans/2026-08-17-phase2-trips.md`](superpowers/plans/2026-08-17-phase2-trips.md)

| Phase | 범위 | 상태 |
|---|---|---|
| 1 | 기반 — 스키마·인증·SPA 골격·배포 | 완료 |
| 2 | 출장 — 신청·목록·상세·수정·결재·타임라인·알림 | **완료** |
| 3 | 정산 — 카드내역·자동매칭·정산서·FC/CC | 다음 |
| 4 | 개발자 — API Key·스코프·`/developers` 가이드 | 대기 |
| 5 | 운영 — Admin CRUD, 반응형, 배포 검증 | 대기 |

**테스트**: 백엔드 293건 · 프론트 45건 · 타입체크 0 errors / 0 warnings · 빌드 성공

---

## Phase 1 — 완료

18개 태스크를 태스크마다 구현 1 + 독립 리뷰 2(사양 준수 / 코드 품질) 방식으로 진행했다.

| 영역 | 내용 |
|---|---|
| 백엔드 | FastAPI 3계층, 14테이블 스키마, 공통코드 검증, 상태전이 표, bcrypt+JWT, `/auth/login`·`/auth/me`, 통일 에러 계약, 멱등 시드 CLI, 외부 운영 DB 접속 |
| 프론트엔드 | SvelteKit 2 / Svelte 5 SPA, DESIGN.md 토큰(primary만 SK온 레드 `#EA002C`), Pretendard, 기본 컴포넌트 4종, 앱 셸, API 클라이언트·인증 스토어, 로그인·라우트가드·대시보드 |
| 배포 | Dockerfile 2종, ingress nginx, 3서비스 compose (DB는 스택 밖) |

**14테이블**: `department` `user` `code_group` `code` `fund_center` `cost_center` `trip` `corporate_card` `card_transaction` `expense_report` `expense_item` `api_key` `notification` `activity_log`

**시드 규모**: 부서 4 · 사용자 14 · 공통코드 9그룹 · FC 6 · CC 10 · 카드 14 · 카드거래 785 · 출장 40 · 정산서 12

---

## Phase 2 — 완료

29개 태스크. Task 1–4는 태스크마다 구현 1 + 독립 리뷰 2 방식으로, Task 5 이후는 인라인 구현 + 태스크별 mutation 검증으로 진행했다.

### 백엔드 — 서비스 계층

| 모듈 | 책임 |
|---|---|
| `services/codes.py` | `validate_codes` 오케스트레이터 — 코드값 여러 개를 **쿼리 2개**로 한 번에 검증. 그룹 조회 + 코드 일괄 조회. `load_code_groups`·`load_code_group` 조회 |
| `services/centers.py` | 활성 센터 코드 로드, `assert_cost_center`, `load_active_centers` |
| `services/trip_rules.py` | 순수 도메인 규칙 10종 + `TRANSITION_ACTOR` 표 + `assert_transition_allowed`. DB 접근 없음 |
| `services/numbering.py` | `BT-YYYY-NNNN` 채번 (연도별) |
| `services/history.py` | `record_transition` — `ActivityLog` + `Notification` 단일 기록 지점 |
| `services/trips.py` | 조회·목록·생성·수정·삭제·전이 5종·타임라인. 스키마를 반환한다 |
| `services/notifications.py` | 알림 목록(전체 미읽음 수 포함)·읽음 처리 |

### 백엔드 — API

```
GET|POST         /api/v1/trips
GET|PATCH|DELETE /api/v1/trips/{id}
POST             /api/v1/trips/{id}/submit | approve | reject | reopen | complete
GET              /api/v1/trips/{id}/timeline
GET              /api/v1/codes  ·  /api/v1/codes/{group_code}
GET              /api/v1/fund-centers  ·  /api/v1/cost-centers
GET              /api/v1/notifications
POST             /api/v1/notifications/{id}/read
```

목록 필터: `scope`(mine·approvals·all) · `status`(반복 파라미터) · `destination_type_code` · `country_code` · `q` · `start_date_from` · `start_date_to` · `page` · `size`

### 프론트엔드

| 항목 | 내용 |
|---|---|
| 화면 | `/trips` `/trips/new` `/trips/[id]` `/trips/[id]/edit` `/approvals` `/notifications` + 대시보드 실데이터 |
| 컴포넌트 | `Select` `Textarea` `EmptyState` `StatusBadge` `TripCard` `FilterBar` `Timeline` `TripForm` |
| 데이터 계층 | `authRequest` 래퍼 + 전역 401, `nav.ts`(딥링크·공개경로), `format.ts`, `trip-status.ts`, API 클라이언트 4종 |
| 앱 셸 | 결재함 링크(MANAGER·ADMIN 한정) + 알림 벨 뱃지. 가운데 3-탭은 DESIGN.md 규칙이라 유지 |

DESIGN.md 매핑: `property-card` → 출장 카드, `search-bar-pill` + `search-orb` → 목록 필터, `reservation-card` → 상세 우측 sticky 액션 카드, `guest-favorite-badge` → 상태 뱃지.

### 실서버 검증 완료

curl로 `BT-2026-0041` 생성 → 상신 → 결재자(김연구) 알림 도착 → 결재함 노출 → 승인 → 타임라인 `CREATED·SUBMITTED·APPROVED`. 웹 UI와 Agent가 물리적으로 같은 엔드포인트를 쓴다는 핵심 메시지가 실제로 성립한다.

에러 계약 실측: 중복 상신 409 `TRIP_INVALID_TRANSITION` · 잘못된 코드값 400 `INVALID_CODE`+`field` · 금액 오버플로 400 `INVALID_AMOUNT` · 타인 출장 404 `TRIP_NOT_FOUND`.

### 설계에서 벗어난 결정

- **`POST /trips/{id}/reopen` 추가.** spec 7의 엔드포인트 목록에는 없지만 spec 5.4 상태도의 `REJECTED → DRAFT`가 요구한다. 없으면 반려된 출장이 영원히 반려 상태로 남는다.
- **`validate_codes`에 `asyncio.gather`를 쓰지 않았다.** Phase 1 이월 메모가 제안했으나 `AsyncSession`은 동시 사용이 금지돼 있어 같은 세션에 `execute`를 병렬로 걸면 `InvalidRequestError`가 난다. 그룹 수와 무관하게 쿼리 2개로 끝내는 방식으로 대체했고, 이쪽이 더 빠르고 안전하다.

---

## Phase 2 리뷰가 잡아낸 결함

전부 mutation testing으로 실증했다 — 코드를 고의로 망가뜨렸는데 테스트가 전부 통과하면 그 테스트는 아무것도 지키지 않는 것이다.

| # | 결함 | 실제 영향 |
|---|---|---|
| 1 | `assert_deletable`을 뒤집어도 27건 전부 통과 | **SETTLED 출장이 삭제 가능**해지는데 아무 테스트도 안 걸림. 6개 상태 중 2개만 덮여 있었다 |
| 2 | `estimated_cost` 상한 없음 | `Numeric(14,2)` 오버플로가 flush에서 터져 **500 INTERNAL_ERROR**. Agent는 5xx를 재시도하므로 절대 성공할 수 없는 요청에 재시도 루프가 걸린다 |
| 3 | 전이 적법성과 권한이 분리 | 한쪽을 빠뜨리면 **fail-open**. `load_visible_trip`을 통과한 결재자가 신청자 전용 전이를 수행할 수 있었다 |
| 4 | `validate_codes`의 `is_active` 필터 2개 | 각각 지워도 127건 전부 통과. 관리자가 코드를 비활성화해도 그 값으로 쓰기가 통과 |
| 5 | `UNKNOWN_CODE_GROUP`이 `field`를 버림 | 코드 필드 5개 중 어디를 고쳐야 하는지 알 수 없는 400 |
| 6 | 파생 테스트 데이터가 검사 대상 상수에서 나옴 | `EDITABLE_STATUSES`를 넓히는 버그가 테스트를 통과 (45 → 44로 조용히 줄기만 함) |
| 7 | `make_trip_master_data`가 seed와 충돌 | `seeded` 세션에서 부르면 `UniqueViolation`이 savepoint 안에서 터져 세션이 오염되고 이후 모든 문장이 `PendingRollbackError`가 되어 원인이 묻힌다 |
| 8 | 팩토리 조직 모양이 seed와 다름 | 매니저와 보고자가 다른 부서에 배정 — 부서로 거르는 기능이 생기면 `seeded` 테스트만 통과 |

3번이 가장 컸다. `TRANSITION_ACTOR` 표 + import 시점 소진 가드로 닫았다 — 새 전이를 추가하고 주체를 빠뜨리면 조용히 "아무나 가능"이 되는 게 아니라 import에서 죽는다.

---

## Phase 3 — 정산

### 범위

카드내역, 자동매칭, 정산서 작성·제출·결재, Fund Center / Cost Center 계층.

**라우트**: `/cards` `/expenses` `/expenses/[id]`

**API**:

```
GET    /api/v1/cards  ·  /api/v1/card-transactions
GET    /api/v1/expenses  ·  POST /api/v1/expenses          (trip_id로 생성)
GET    /api/v1/expenses/{id}
GET    /api/v1/expenses/{id}/match-candidates              ← 자동매칭 후보 + 사유
POST   /api/v1/expenses/{id}/items
PATCH|DELETE /api/v1/expense-items/{id}
POST   /api/v1/expenses/{id}/submit | approve | reject
```

### 핵심 작업

**자동매칭 (`services/matching.py`)** — DB 접근 없는 순수 함수로 구현한다. 입력은 trip + 거래 리스트. 후보 조건:

- 해당 사용자 카드의 거래
- `approved_at`이 `start_date - 1일 ~ end_date + 1일` 범위
- `is_cancelled = false`
- 다른 제출완료(`SUBMITTED` 이상) 리포트에 포함되지 않았을 것

각 후보에 매칭 사유 문자열(`출장기간 내 승인`, `출발 전일 교통비` 등)을 붙여 UI와 API 양쪽에 동일하게 노출한다.

**FC/CC 계층** — `expense_report`가 기본값을 갖고 `expense_item`의 FC/CC는 nullable override다. 비어 있으면 리포트 값을 사용한다(`coalesce`). `cost_center_code`는 출장에서 정산서로 승계되며 수정 가능하다. 정산서 제출 시 FC/CC가 비어 있으면 검증 실패다.

**정산서 생성 제약** — `trip.status`가 `APPROVED` 또는 `COMPLETED`일 때만 생성 가능하고 `trip_id`가 uniq다(출장당 1건). 그 외 상태에서 시도하면 409.

**`COMPLETED → SETTLED` 전이 연결** — `TRANSITION_ACTOR`에 `SYSTEM`으로 등록돼 있고 현재 모든 직접 호출을 `SYSTEM_TRANSITION_ONLY`로 막는다. 정산서가 `APPROVED`로 갈 때 서비스가 이 전이를 수행해야 하며, **반드시 `record_transition`을 통과시킨다** — 출장 쪽 이력이 비면 타임라인이 끊긴다. 시스템 전이를 어떻게 통과시킬지(전용 함수 추가 vs `assert_transition_allowed` 우회 경로)를 먼저 정하고 시작할 것.

### Phase 2에서 넘어온 항목

**서비스 계층 정리 — Phase 3 착수 전에**

- **`load_active_codes`의 생산 호출부가 사라졌다.** `validate_codes` 도입 이후 이 함수를 부르는 것은 테스트뿐이다. 그런데 "그룹 부재 vs 활성 코드 0개" 규칙과 `is_active` 필터 2개가 이제 두 벌의 쿼리 구현에 각각 들어 있어, 의미를 바꾸려면 두 곳을 다 찾아야 한다. 둘 중 하나를 택한다 — (a) `load_active_codes`와 딸린 테스트 3건 삭제, (b) 두 함수를 `_load_active_codes_by_group(session, group_codes) -> dict[str, set[str]]` 하나 위에 얹기.
- **그때 `load_active_codes`의 주석도 고친다.** "join은 두 경우를 구분하지 못한다"고 적혀 있으나 이는 **inner** join에만 참이다. LEFT OUTER JOIN은 구분할 수 있다(그룹 없음 → 행 없음, 코드 0개 → `(group, NULL)`). 지금 구조를 바꿀 이유는 없지만 저 문장은 언젠가 누군가를 오도한다.
- **`assert_fund_center`가 없다.** `services/centers.py`에 코스트센터 검증만 있다. 정산서 쓰기 경로가 첫 사용처다. **그때 순수 함수를 뽑는다** — 지금 `assert_cost_center`는 쿼리·멤버십 검사·예외 발생이 한 함수에 붙어 있어 두 줄짜리 순수 검사에 `db_session`이 필요하다. `assert_fund_center`가 `if code not in allowed: raise` 블록을 복사하려는 순간이 `assert_center_code(code, allowed, *, field)`를 뽑을 시점이다.
- **`GET /fund-centers`는 만들어만 뒀다.** Phase 2에서 화면이 쓰지 않는다. 정산서 헤더의 FC 셀렉트가 첫 사용처다.
- **`ActivityAction`에 정산 액션이 없다.** 현재 enum은 출장 기준이다. 정산서 전이도 같은 `activity_log`를 쓰되 `entity_type=EXPENSE_REPORT`로 구분한다. 새 액션 멤버가 필요한지 Phase 3에서 판단한다.

**UI**

- **브라우저 시나리오 8개 미확인.** 딥링크 보존, 중복 제출 가드, 반려→재작성→재상신 UI, 전역 401 정리. 코드와 단위테스트로는 덮여 있으나 실브라우저로 눌러보지 않았다. 절차는 Phase 2 계획 Task 29 Step 3에 있다.
- **알림 뱃지는 라우트 변경 시에만 갱신된다.** 같은 화면에 머무는 동안 새 알림이 오면 보이지 않는다. 폴링·SSE는 데모 범위 밖이라 하지 않았다.
- **대시보드가 집계를 위해 목록 API를 4번 부른다.** `size=1`이라 비용은 작지만 카드가 더 늘면 전용 요약 엔드포인트가 낫다.
- **새 폼마다 중복 제출 가드** (`if (submitting) return;`). 정산서 제출도 멱등하지 않다.

**기타**

- **`q` 필터는 LIKE 와일드카드를 이스케이프하지 않는다.** 사용자가 `%`를 넣으면 검색 범위가 넓어질 뿐이지만, 정확도가 중요한 검색을 만들면 그때 처리한다.
- **출장번호 채번은 `max() + 1`이다.** 단일 인스턴스 전제. `trip_no` unique 제약이 마지막 방어선이다(그 경우 500). 멀티 레플리카로 가면 시퀀스나 advisory lock이 필요하다.
- **`restore()`/`clear()` 경합은 여전히 도달 불가.** `AppShell`은 `auth.user`가 non-null일 때만 마운트된다. "세션 갱신" 같은 호출이 생기면 그때 정리한다.

---

## 이후 Phase

| Phase | 범위 |
|---|---|
| 4 | 개발자 — API Key 발급·폐기·스코프, `/developers` 가이드, OpenAPI 정리 |
| 5 | 운영 — Admin(공통코드·센터·사용자·부서·카드), 반응형, 배포 재검증 |

**Phase 4 착수 시 반드시 볼 것**: `app/deps.py`가 JWT 인증에서 `request.state.scopes = UNRESTRICTED`(전용 센티널)를 넣는다. 스코프 검사기는 이 값을 **센티널과 동일성 비교**해야 하며, `getattr(request.state, "scopes", None)`처럼 기본값을 두고 "값이 없으면 통과" 식으로 쓰면 안 된다. 그러면 "제한 없음"과 "`get_principal`이 아예 실행되지 않음"이 구분되지 않아, 의존성을 빠뜨린 엔드포인트가 조용히 전체 권한을 얻는 fail-open이 된다.

## 전 Phase 공통 미결

- **반응형**: DESIGN.md의 744px 미만 햄버거·시트 붕괴가 미구현이다. 744px에서는 정상이나 375px에서 탭이 두 줄로 깨지고 우측 블록이 화면 밖으로 나간다. 데스크톱 데모 기준이라 의도적으로 넘겼고 뼈대가 하나도 없으므로 해당 Phase에서 처음부터 만들어야 한다. Phase 2에서 화면이 6개 늘어 작업량이 그만큼 커졌다.
- **비밀번호 길이**: bcrypt 5.x는 72바이트 초과 시 자르지 않고 예외를 던진다. 한글은 **24자만 넘어도** 터진다. 비밀번호 설정·변경 엔드포인트를 만들 때 요청 스키마에서 막아야 한다.
- **운영 `JWT_SECRET`**: compose 기본값은 명백한 placeholder다. 배포 시 32바이트 이상 실제 값을 `.env`로 주입한다.
- **`init-db`는 컬럼 변경을 반영하지 않는다.** Alembic을 쓰지 않으므로 스키마를 바꾸면 해당 테이블을 지우고 다시 돌려야 한다. 실제 운영 전환이 필요해지면 마이그레이션 도구 도입을 재검토한다.
