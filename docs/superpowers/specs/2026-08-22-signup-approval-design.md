# 회원가입 · 관리자 승인

작성일 2026-08-22. Phase 5 이후의 후속 기능.

## 배경

지금 계정을 만드는 경로는 관리자 화면(`/admin/users`)의 생성 폼 하나뿐이다. 데모를 외부에
열어두면 써 보려는 사람이 계정을 얻을 방법이 없고, 관리자가 매번 손으로 만들어야 한다.

반대로 아무나 가입해서 바로 쓰게 두면 사번·부서·결재자가 채워지지 않는다. 그 세 값은 출장
결재선과 정산 귀속의 근거이고, 본인이 고르면 틀린다 — 사번은 외부인이 알 수 없고, 결재자는
조직 정보다.

그래서 **가입은 열되 승인은 관리자가 한다.** 가입자는 최소 정보만 내고, 관리자가 승인 시점에
조직 정보를 채운다. 즉 승인은 "확인"이 아니라 "배치"다.

유저 관리 자체는 이미 있다(`routers/admin/users.py` — 목록·생성·조회·수정·비밀번호설정,
`/admin/users` 화면). 이 문서가 더하는 것은 **가입 경로와 승인 전이**뿐이다.

## 선행 조건

`docs/migrations/2026-08-21-user-table-to-public.sql`이 먼저 실행되어야 한다. 이 문서의
마이그레이션은 `public."user"`를 대상으로 하며, 이관 전 DB에서는 대상 테이블이 없다.

## 1. 상태 모델

### UserStatus

`app/enums.py`에 추가한다. 공통코드 테이블이 아니라 Python Enum인 이유는 기존 규칙과 같다 —
가입·승인·로그인 분기에 박히는 값이므로 관리자가 편집할 수 있으면 안 된다.

```python
class UserStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
```

### status와 is_active의 분리

두 값의 의미를 겹치지 않게 고정한다.

- `status` — 가입 신청의 생애주기. 이 프로젝트만 읽는다.
- `is_active` — 로그인 가능 여부. **의미를 바꾸지 않는다.**

**불변식: `status != ACTIVE` ⟹ `is_active = false`** (단방향).

역은 성립하지 않는다. 승인된 뒤 관리자가 정지시킨 사용자는 `status=ACTIVE` + `is_active=false`
이고, 이것이 "승인 대기"와 구분되어야 하는 바로 그 경우다.

단방향으로 둔 대가가 이 설계의 핵심 이득이다. `is_active`의 의미가 그대로이므로
**로그인 게이트도, 계정을 공유하는 상대 프로젝트가 보는 시야도 바뀌지 않는다.** 상대
프로젝트는 `status`를 몰라도 우리 PENDING 사용자를 "비활성"으로 올바르게 읽는다.

## 2. 스키마 변경

`public."user"`에 세 건. `docs/migrations/2026-08-22-user-signup-status.sql`로 쓰고, Alembic을
쓰지 않으므로 **사람이 psql로 한 번 실행한다.**

| 컬럼 | 변경 | 이유 |
| --- | --- | --- |
| `status` | 신규 `varchar(20)` NOT NULL DEFAULT `'ACTIVE'` | 기존 14행이 DEFAULT로 ACTIVE가 된다 |
| `employee_no` | NOT NULL 해제 | 가입 시점에 값이 없다 |
| `position_code` | NOT NULL 해제 | 같음 |

`status`는 `role`과 같이 `SAEnum(..., native_enum=False, length=20)`으로 매핑한다. 공유
테이블에 PostgreSQL enum 타입을 만들면 상대 프로젝트가 우리 스키마의 타입 이름에 묶인다.

`employee_no`의 unique 제약은 **유지한다.** NULL은 Postgres unique에서 서로 충돌하지 않으므로
대기 행이 여럿이어도 문제가 없다.

### 임시값을 쓰지 않는 이유

`employee_no`에 `PENDING-<uuid>` 같은 값을 채우는 선택지도 있었다. 거부한 이유는 그 가짜 사번이
상대 프로젝트·기존 유저 관리 화면·Agent API에 **실제 사번처럼 노출**되기 때문이다. NULL은
"없다"를 정직하게 말한다. `position_code`도 같다 — 임시값을 쓰면 공통코드 검증을 통과시키려고
센티널 코드를 마스터에 넣어야 하고, 그 코드가 관리자 코드 관리 화면과 직급 드롭다운에 나타난다.

값이 있어야 하는 시점(`ACTIVE`로의 승인)은 서비스가 강제한다.

## 3. 전이

기존 출장·정산과 같은 구조를 쓴다. 적법성과 수행 주체를 따로 부를 수 있게 열어두지 않고
**단일 assert 하나만 통과**시킨다. 이유도 같다 — 나뉘어 있으면 언젠가 한쪽만 부르고, 그
실패는 fail-open이다.

```
PENDING  → ACTIVE     (관리자 승인)
PENDING  → REJECTED   (관리자 거절)
REJECTED → PENDING    (본인 재신청)
ACTIVE   → (없음)
```

`ACTIVE`에서 나가는 전이가 없으므로 승인된 계정에 `approve`를 다시 호출하면 409다. 계정 정지는
전이가 아니라 기존 `PATCH /admin/users/{id}`의 `is_active` 변경으로 남는다.

주체는 승인·거절이 관리자, 재신청이 미인증 가입자다. 표에 전이를 추가하고 주체를 빠뜨리면
임포트 시점에 `RuntimeError`로 죽어야 한다.

## 4. 백엔드 API

### 미인증

`get_principal`을 지나지 않으므로 `SCOPE_REQUIREMENTS`에 넣지 않는다. 소진 가드는 인증
라우트만 대조하므로 표에 없는 것이 맞다.

**`POST /api/v1/auth/signup`**

받는 값: `email` · `password` · `name` · `department_id`.

만드는 행: `status=PENDING`, `is_active=false`, `role=EMPLOYEE`, `employee_no=NULL`,
`position_code=NULL`, `manager_id=NULL`.

**응답에 토큰을 넣지 않는다.** 승인 전에는 로그인할 수 없으므로 토큰을 주면 거짓말이 된다.
201과 안내 메시지만 반환한다.

`password`는 `assert_password_length`를 지난다(bcrypt 72바이트). `department_id`는
`_assert_department`로 존재를 확인한다.

이메일이 이미 있을 때의 분기:

| 기존 행의 status | 동작 |
| --- | --- |
| `REJECTED` | 그 행을 `PENDING`으로 되돌리고 이름·부서·비밀번호를 덮어쓴다 (재신청) |
| `PENDING` | 409 `ALREADY_PENDING`. 덮어쓰지 않는다 |
| `ACTIVE` | 409 `DUPLICATE_EMAIL` |

`PENDING`을 덮어쓰지 않는 것이 중요하다. 덮어쓰기를 허용하면 남이 신청해 둔 대기 계정에
**내가 아는 비밀번호를 덮어씌운 뒤 승인을 기다려 계정을 가로챌 수 있다.** `REJECTED`는 이미
관리자가 거부한 행이라 같은 위험이 없다.

**`GET /api/v1/auth/departments`**

`id` · `name`만 반환한다. 가입 폼의 부서 드롭다운 때문에 필요하다 — 현재 부서 목록은
`/api/v1/admin/departments`(admin 스코프)뿐이라 미인증 가입자가 쓸 수 없다.

부서명이 로그인 없이 보이는 것은 의도된 노출이다. 데모 조직도이고, 대안(부서를 관리자가
승인 시점에 고르게 하기)은 가입자가 자기 소속을 아는데도 못 적게 만든다.

### 관리자

`SCOPE_REQUIREMENTS`에 두 줄을 **같은 커밋에서** 추가한다. 빠뜨리면 앱이 뜨지 않는다.

```python
("POST", "/api/v1/admin/users/{user_id}/approve"): _AD,
("POST", "/api/v1/admin/users/{user_id}/reject"): _AD,
```

**`POST /api/v1/admin/users/{user_id}/approve`**

받는 값: `employee_no` · `position_code` · `manager_id`(nullable) · `role`.

검증은 `create_user`의 것을 그대로 쓴다 — 사번 unique(`assert_unique`), 직급 공통코드
(`validate_codes`의 `POSITION` 그룹), 결재자 존재·자기참조 금지(`_assert_manager`).

성공 시 `status=ACTIVE`, `is_active=true`.

**`POST /api/v1/admin/users/{user_id}/reject`**

`status=REJECTED`, `is_active=false`. 행은 지우지 않는다. 거절 이력이 남고, 이메일 unique
제약과 충돌하지 않으며, 재신청 경로가 생긴다.

두 라우트 모두 `AdminUser`(role=ADMIN)를 지난다. 역할과 스코프를 둘 다 통과하는 기존 Admin
규칙 그대로다.

### 응답·필터 확장

- `AdminUserOut`에 `status` 추가
- `AdminUserCreate`에는 추가하지 않는다 — 관리자가 직접 만든 계정은 항상 `ACTIVE`다
- `AdminUserUpdate`에도 추가하지 않는다 — `status` 변경은 전이 엔드포인트만 한다. `PATCH`로
  바꿀 수 있으면 전이 가드를 우회하는 두 번째 경로가 생긴다
- `UserFilters`에 `status: UserStatus | None` 추가, `GET /admin/users`에 쿼리 파라미터 추가
- `employee_no` · `position_code`가 nullable이 되었으므로 `AdminUserOut`의 두 필드도
  `str | None`이 된다

### 파일 배치

3계층을 그대로 지킨다. 라우터에 로직을 두지 않는다.

| 파일 | 역할 |
| --- | --- |
| `app/services/user_status.py` | 전이 표 · 주체 표 · 단일 `assert_signup_transition_allowed` |
| `app/services/signup.py` | 가입 · 부서 목록. 미인증 경로 |
| `app/services/admin/users.py` | `approve_user` · `reject_user` 추가 |
| `app/routers/auth.py` | `POST /signup` · `GET /departments` 추가 |
| `app/routers/admin/users.py` | `POST /{id}/approve` · `POST /{id}/reject` 추가 |

`_assert_department` · `_assert_manager` · `assert_unique`는 지금 `services/admin/users.py`에
있다. `signup.py`가 부서 검증을 쓰므로 `_assert_department`를 `services/admin/common.py`로
옮기고 양쪽이 같은 함수를 부른다. 복사하지 않는다 — 검증이 두 벌이 되면 한쪽만 고쳐진다.

### 시드

`app/seed.py`에 `PENDING` 사용자 한 명을 추가한다. 승인 화면을 시연하려면 대기 건이 있어야
하고, 없으면 데모마다 사람이 손으로 가입해야 한다. 시드는 멱등해야 하므로 이메일로 존재를
확인하고 건너뛴다. 기존 14계정은 모두 `ACTIVE`다.

## 5. 로그인

`is_active=false`이므로 대기·거절 사용자는 지금 코드로도 이미 로그인이 막힌다. 바뀌는 것은
**메시지뿐**이다.

현재 로그인은 계정 존재 여부가 새지 않도록 에러 코드를 통일하고, 없는 계정에도 더미 해시로
bcrypt를 태워 응답 시간까지 맞춘다. 그 방어를 유지한 채 안내만 더한다:

**비밀번호 검증이 성공한 뒤에만** `status`를 본다.

- `PENDING` → 401 `PENDING_APPROVAL` ("관리자 승인 대기 중입니다")
- `REJECTED` → 401 `SIGNUP_REJECTED`
- 그 외 `is_active=false` → 기존 `INVALID_CREDENTIALS`

비밀번호를 맞힌 사람에게만 상태를 알리므로 계정 존재가 새지 않는다. 비밀번호를 모르는
공격자에게는 응답이 지금과 완전히 같다.

순서가 중요하다. `status`를 비밀번호 검증 **앞에서** 보면 이메일만으로 계정 존재가 드러난다.

## 6. 프론트

**`/signup`** (신규, 미인증)

이메일 · 이름 · 비밀번호 · 부서 드롭다운. 부서는 `GET /auth/departments`로 채운다.

`handleSubmit` 첫 줄에 `if (submitting) return;`. 가입은 멱등하지 않아 중복 POST가 곧 중복
계정 시도다. 호출은 미인증이므로 `authRequest`가 아니라 raw `request`를 쓴다 — `login`과 같은
부류이며, 이 두 경로 외에 raw `request`를 늘리지 않는다.

성공 시 폼을 안내 문구로 교체한다("승인 후 로그인할 수 있습니다"). 자동 로그인은 하지 않는다.

**`/login`**

가입 링크를 추가하고, `PENDING_APPROVAL` · `SIGNUP_REJECTED` 코드에 각각 안내 문구를 매핑한다.

**`/admin/users`**

- 목록에 `status` 표시, 상태 필터 추가 (`FilterBar`)
- `PENDING` 행에만 [승인] [거절]
- 승인은 `Modal.svelte`로 연다. 사번 · 직급 · 결재자 · 역할 입력. 백드롭 클릭 판정은
  `event.target === dialog`
- 모달 안에 입력이 여러 개이므로 `$props.id()`는 한 번만 부르고 접미사를 붙인다
  (`FilterBar.svelte` 패턴)
- 목록·에러·중복제출 가드는 기존 `AdminResource`를 쓴다
- 반응형 분기는 `tablet:`(744px)
- `text-body`를 쓰지 않는다 — `text-body-sm` / `text-body-md`
- `crypto.randomUUID()` 등 SecureContext 전용 API를 쓰지 않는다 (운영은 평문 HTTP)

## 7. 테스트

백엔드:

- 가입 성공 → `PENDING` · `is_active=false` · `employee_no is None`
- 이메일 중복 3분기 각각 (`REJECTED` 재신청 성공 / `PENDING` 409 / `ACTIVE` 409)
- **`PENDING` 덮어쓰기 거부** — 이 가드가 계정 탈취를 막으므로 mutation으로 확인한다
- 승인: 사번 중복 · 없는 직급 · 없는 결재자 · 자기 자신 결재자 각각 거부
- 승인 후 `status=ACTIVE` · `is_active=true` · 로그인 성공
- 전이 가드: `ACTIVE`에 `approve` 재호출 409, `ACTIVE`에 `reject` 409
- 로그인: `PENDING` 계정 + **올바른 비밀번호** → `PENDING_APPROVAL`
- 로그인: `PENDING` 계정 + **틀린 비밀번호** → `INVALID_CREDENTIALS` (상태가 새지 않음)
- `PATCH /admin/users/{id}`로 `status`를 바꿀 수 없음
- 스코프 표 완전성은 기존 `assert_scope_table_complete`가 자동으로 잡는다

전이 표와 주체 표를 리터럴에서 파생시킨다. `set(UserStatus) - {...}` 식으로 쓰면 표를 넓히는
버그와 테스트가 함께 움직여 통과한다.

프론트: 기존 정책대로 순수 모듈만. jsdom을 추가하지 않는다.

## 8. 하지 않는 것

- **이메일 인증·발송** — SMTP 의존이 생기고 데모 범위를 넘는다
- **rate limit** — `POST /auth/signup`은 미인증 쓰기 엔드포인트라 스팸 가입이 가능하다.
  데모 범위로 생략하되 `docs/phase-status.md`의 이월 항목에 적는다
- **셀프 비밀번호 재설정** — 관리자의 `POST /admin/users/{id}/password`가 이미 있다
- **가입 알림 · 대기 건수 배지** — `NotificationType`은 본인 대상으로 설계되어 있어 관리자
  대상 알림은 구조가 다르다. 관리자 UI를 `/admin/users` 한 곳으로 정했으므로 별도 큐 배지도
  만들지 않는다
- **가입 활동 로그** — `EntityType`에 `USER` 멤버가 없다. 키 발급·Admin 마스터 변경이 로그에
  남지 않는 기존 이월 항목과 같은 건이며, 함께 처리한다

## 9. 문서 갱신

- `CLAUDE.md` — `status`/`is_active` 불변식과 그 이유, 로그인의 검증 순서, `PATCH`로 `status`를
  바꾸지 않는다는 사실
- `docs/phase-status.md` — rate limit 미적용을 이월 항목에 추가
- `docs/manual-scenarios.md` — 가입 · 승인 · 거절 · 재신청 시나리오 추가
