# Phase 현황 — 완료분과 다음 작업

- 기준: Phase 3 (정산) 완료 시점
- 설계: [`superpowers/specs/2026-08-12-skon-biztrip-web-design.md`](superpowers/specs/2026-08-12-skon-biztrip-web-design.md)
- Phase 1 계획: [`superpowers/plans/2026-08-12-phase1-foundation.md`](superpowers/plans/2026-08-12-phase1-foundation.md)
- Phase 2 계획: [`superpowers/plans/2026-08-17-phase2-trips.md`](superpowers/plans/2026-08-17-phase2-trips.md)
- Phase 3 계획: [`superpowers/plans/2026-08-18-phase3-expenses.md`](superpowers/plans/2026-08-18-phase3-expenses.md)

| Phase | 범위 | 상태 |
|---|---|---|
| 1 | 기반 — 스키마·인증·SPA 골격·배포 | 완료 |
| 2 | 출장 — 신청·목록·상세·수정·결재·타임라인·알림 | 완료 |
| 3 | 정산 — 카드내역·자동매칭·정산서·FC/CC | **완료** |
| 4 | 개발자 — API Key·스코프·`/developers` 가이드 | 다음 |
| 5 | 운영 — Admin CRUD, 반응형, 배포 검증 | 대기 |

**테스트**: 백엔드 408건 · 프론트 55건 · 타입체크 0 errors / 0 warnings · 빌드 성공

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

## Phase 3 — 완료

25개 태스크. Task 1–2는 구현 subagent + 독립 스펙 리뷰로, 나머지는 인라인 구현 + 태스크별 mutation 검증으로 진행했다(예산 한도로 subagent 경로 중단).

### 백엔드 — 서비스 계층

| 모듈 | 책임 |
|---|---|
| `services/matching.py` | 자동매칭 순수 함수 — 창(±1일)·취소·잠금 판정 + 매칭 사유 문자열 + 비목 추천. DB 접근 없음. 날짜는 KST 기준 |
| `services/expense_rules.py` | 정산 순수 규칙 + `EXPENSE_ALLOWED_TRANSITIONS`/`EXPENSE_TRANSITION_ACTOR` 표 + 임포트 시점 소진 가드 + `assert_expense_transition_allowed` |
| `services/expenses.py` | 정산서 조회·목록·생성·헤더수정·항목 CRUD·매칭후보·전이 4종·타임라인 |
| `services/cards.py` | 내 법인카드·카드거래 조회 (소유자 필터는 서비스가 건다) |
| `services/centers.py` | `assert_center_code` 순수 함수 추출, `assert_fund_center` 추가 |
| `services/trips.py` | `settle_trip_for_report` 추가 — commit하지 않는 시스템 전이 |
| `services/trip_rules.py` | `assert_system_transition` 추가 — 사용자 주체 전이를 거부하는 통로 |

### 백엔드 — API

```
GET              /api/v1/cards  ·  /api/v1/card-transactions
GET|POST         /api/v1/expenses
GET|PATCH        /api/v1/expenses/{id}
GET              /api/v1/expenses/{id}/match-candidates  ·  /timeline
POST             /api/v1/expenses/{id}/items
PATCH|DELETE     /api/v1/expense-items/{id}
POST             /api/v1/expenses/{id}/submit | approve | reject | reopen
```

정산 목록 필터: `scope`(mine·approvals·all) · `status`(반복 파라미터) · `q` · `page` · `size`
카드거래 필터: `card_id` · `approved_from` · `approved_to` · `merchant_category_code` · `q` · `include_cancelled` · `page` · `size`

### 프론트엔드

| 항목 | 내용 |
|---|---|
| 화면 | `/cards` `/expenses` `/expenses/[id]` + 출장 상세의 정산 진입 + 대시보드 미정산 카드 연결 |
| 컴포넌트 | `ExpenseStatusBadge` `CardTransactionTable` `MatchPanel` `ExpenseItemsTable` |
| 데이터 계층 | `api/query.ts`(공용 쿼리스트링 빌더, `tripQueryString`도 여기로 위임) · `api/cards.ts` · `api/expenses.ts` · `lib/expenses.ts`(상태 라벨·`resolveCenter`·`sumIncluded`) |

DESIGN.md 매핑: `reservation-card` → 정산서 우측 sticky 액션 카드, `rating-display`(64px = `text-display-xl`) → 정산 총액.

### 확정한 설계 결정

| 쟁점 | 결정 |
|---|---|
| `COMPLETED → SETTLED` 통로 | `assert_system_transition` 신설. 같은 `TRANSITION_ACTOR` 표를 읽고 양방향 fail-closed — 사용자 경로는 SYSTEM 전이를, 시스템 경로는 OWNER/APPROVER 전이를 거부 |
| 출장 이력 | `settle_trip_for_report`가 `record_transition`을 통과하고 commit하지 않는다 (정산 승인과 한 트랜잭션) |
| 반려 흐름 | `REJECTED` 후 `reopen`으로 DRAFT 복귀 (출장과 대칭). spec 5.5의 "반려 시 DRAFT" 문구보다 반려 사유 표시를 우선 |
| 제출 시 출장 상태 | 생성은 APPROVED·COMPLETED, **제출은 COMPLETED만**. 아니면 승인 시점에 전이표에 없는 `APPROVED → SETTLED`가 필요해진다 |
| `ActivityAction` | 정산 전용 멤버를 추가하지 않고 `entity_type=EXPENSE_REPORT`로 구분 |
| 승인 알림 | 정산서 쪽 `EXPENSE_APPROVED` 하나만. 출장 SETTLED는 activity_log만 남긴다 |
| 금액 상한 | 항목(`MAX_ITEM_AMOUNT`)과 합계(`MAX_REPORT_TOTAL`) 둘 다 서비스가 막는다 |
| 매칭 날짜 | `approved_at`을 KST로 변환해 비교 |

### 설계에서 벗어난 결정

- **`PATCH /expenses/{id}` 추가.** spec 7 목록에 없지만 spec 5.5가 "cost_center_code는 승계되며 수정 가능"과 "제출 시 FC/CC 필수"를 동시에 요구한다. 헤더를 고칠 경로가 없으면 FC가 빈 정산서는 영원히 제출 불가다.
- **`POST /expenses/{id}/reopen` 추가.** 출장의 reopen과 같은 이유.
- **`GET /expenses/{id}/timeline` 추가.** 쓰기만 하고 아무도 읽지 않는 `activity_log`가 되지 않도록.
- **`POST /items`·`PATCH|DELETE /expense-items/{id}`가 갱신된 정산서를 돌려준다.** 합계와 항목이 함께 바뀌므로 재조회 왕복을 없앤다.

### 시드 결함 수정

정산서를 COMPLETED 출장부터 채우던 탓에 **SETTLED 출장 일부가 정산서 없이** 남았다. SETTLED는 정산서가 승인됐다는 뜻이므로 상태 정의와 모순이고, 정산서 생성 시나리오도 막혔다. SETTLED를 먼저 채우고 남는 자리를 COMPLETED로 메우도록 고쳤다(정산서 12건은 그대로). 두 규칙을 `test_seed.py`가 지킨다.

**주의**: 이 수정은 시드 코드의 문제이므로 **이미 적재된 운영 DB에는 반영되지 않는다**(시드는 멱등이라 기존 행을 고치지 않는다). 필요하면 `expense_report`·`expense_item`·`trip`을 지우고 다시 시드해야 한다.

### 실서버 검증 완료

curl로 Agent 경로를 그대로 밟았다: `BT-2026-0020` 완료 처리 → 정산서 `EX-2026-0013` 생성(코스트센터 CC2100 승계) → 항목 추가 → FC 지정 → 제출 → 결재자(김연구) 결재함 노출 → 승인 → **출장이 SETTLED로 자동 전이** → 출장 타임라인 `COMPLETED·SETTLED`, 정산 타임라인 `CREATED·UPDATED·SUBMITTED·APPROVED`, 신청자에게 `EXPENSE_APPROVED` 알림.

자동매칭 실측(`BT-2026-0030`): 후보 6건, 사유 `출장기간 내 승인` 5건 + `종료 익일 승인` 1건, 비목 추천 `TRANSPORT`/`MEAL`/`LODGING`.

에러 계약 실측: 항목 없이 제출 409 `EXPENSE_NO_ITEMS` · FC 없이 제출 400 `CENTER_REQUIRED`+`field` · 신청자의 승인 시도 403 `NOT_EXPENSE_APPROVER` · 중복 승인 409 `EXPENSE_INVALID_TRANSITION` · 승인 후 항목 수정 409 `EXPENSE_NOT_EDITABLE` · 타인 정산서 404 `EXPENSE_NOT_FOUND`.

### Phase 3에서 처리한 이월 항목

- `load_active_codes` 삭제. "그룹 부재 vs 활성 코드 0개" 규칙은 `validate_codes` 테스트가 `field`까지 포함해 지킨다.
- `assert_center_code` 순수 함수 추출 + `assert_fund_center` 추가. 멤버십 검사가 한 곳뿐이다.
- `GET /fund-centers`가 첫 소비처(정산서 헤더 FC 셀렉트)를 얻었다.
- `COMPLETED → SETTLED` 연결 완료.
- `ActivityAction`은 그대로 두기로 결정.

### mutation 검증 목록

가드를 넣을 때마다 그 줄을 망가뜨려 테스트가 실제로 깨지는지 확인했다.

| 가드 | 깨진 테스트 |
|---|---|
| `assert_center_code`의 멤버십 검사 | 7건 |
| `assert_system_transition`의 SYSTEM 검사 | 2건 |
| `matching`의 취소·잠금 필터, `WINDOW_DAYS` | 각 1–2건 |
| `EXPENSE_TRANSITION_ACTOR` 엔트리 삭제 | 임포트 시점 `RuntimeError` |
| `assert_report_total`, `sum_included`의 제외 처리 | 각 1건 |
| 카드거래 소유자 필터 | 1건 |
| `assert_report_creatable` · `assert_trip_owner`(정산서 생성) | 각 1건 |
| `assert_item_amount`, 거래 소유자 조건, 합계 재계산 | 각 1건 |
| 매칭 잠금 상태 집합(DRAFT 포함), 자기 리포트 제외 조건 | 각 1건 |
| `assert_trip_completed` · `assert_has_items` · `assert_centers_present` · `settle_trip_for_report` 호출 | 각 1–3건 |

---

## Phase 3에서 넘어온 항목

**UI**

- **브라우저 수동 시나리오 14개 미확인.** Phase 2 이월 8개(딥링크·중복 제출·반려 재작성·전역 401 등) + Phase 3 신규 6개(카드 필터, 정산서 생성·승계, 담기, 부서 상속 토글, FC 누락 제출, 승인 후 출장 SETTLED 확인). 절차는 Phase 3 계획 Task 24에 있다.
- **출장 상세가 정산서 존재 여부를 목록 `size=100` 조회로 판단한다.** 데모 규모에서는 충분하지만 정산서가 100건을 넘으면 놓친다. `trip_id` 필터나 전용 조회가 필요하다.
- **알림 뱃지는 여전히 라우트 변경 시에만 갱신된다.** 폴링·SSE는 데모 범위 밖.
- **대시보드 집계는 여전히 목록 API 4회 호출이다.**

**백엔드**

- **항목의 FC/CC override는 제출 시 재검증되지 않는다.** 제출은 헤더 FC/CC만 마스터와 대조한다. 항목 override 후 그 센터가 비활성화되면 통과한다.
- **정산 목록의 `q`도 LIKE 와일드카드를 이스케이프하지 않는다** (출장과 같은 판단).
- **`next_report_no`도 `max() + 1`이다.** 멀티 레플리카로 가면 `next_trip_no`와 함께 시퀀스나 advisory lock으로 옮긴다.
- **매칭 후보 조회는 페이징이 없다.** 출장 기간 ±2일이라 건수가 작지만, 장기 출장에서는 커질 수 있다.
- **운영 DB의 기존 시드 데이터는 옛 배정 규칙 그대로다** (위 "시드 결함 수정" 참조).

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
