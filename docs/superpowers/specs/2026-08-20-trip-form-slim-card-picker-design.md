# 출장 신청 필드 축소 · 정산 카드내역 피커

작성일 2026-08-20. Phase 5 이후의 후속 수정 두 건.

## 배경

데모 시연에서 두 가지 마찰이 드러났다.

출장 신청 화면이 신청 시점에 알 수 없는 값을 요구한다. 이동수단·숙박유형·예상비용은
출발 전에 확정되지 않는 경우가 많고, 값을 강제하면 신청자가 아무 값이나 고른다. 코스트센터도
마찬가지로 신청 시점의 관심사가 아니라 정산 시점의 관심사다.

정산 화면은 자동매칭 후보에 든 카드 거래만 담을 수 있다. 매칭 창은 출장 시작 1일 전 ~ 종료
1일 후이므로, 그 밖에서 결제된 출장 비용은 화면에서 담을 방법이 없다. 백엔드는 이미 임의의
본인 카드 거래를 받아들이므로(`_assert_usable_transaction`은 후보 여부를 보지 않는다) 이것은
순전히 화면의 제약이다.

## 1. 출장 필드 축소

### 전면 제거

`transport_code` · `accommodation_code` · `estimated_cost`를 모델·스키마·서비스·시드·프론트·
테스트에서 지운다. 응답 스키마에서도 지우므로 API 계약이 바뀐다 — 데모이며 외부 소비자가
없으므로 버저닝하지 않는다.

`services/trip_rules.py`의 `MAX_ESTIMATED_COST`와 `assert_estimated_cost`도 함께 지운다. 이
가드는 `Numeric(14, 2)` 오버플로가 500이 되는 것을 막으려고 있었고, 컬럼이 사라지면 막을
대상이 없다. `CLAUDE.md`의 해당 문단도 지운다 — 존재하지 않는 방어선을 문서가 가리키면 다음
작업자가 그것을 찾다가 시간을 쓴다.

공통코드 그룹 `TRANSPORT` · `ACCOMMODATION`은 남긴다. 관리자 코드 관리 화면의 데이터이고,
지우면 시드와 관리자 테스트가 함께 흔들린다. 출장에서 참조만 끊는다.

### 코스트센터: 출장 등록에서만 제거

`Trip.cost_center_code` 컬럼은 nullable로 남기고 `TripCreate` · `TripUpdate` · `TripForm`에서만
지운다. 컬럼째 없애지 않는 이유는 `services/expenses.py`의 정산서 생성이 이 값을 승계하기
때문이다. 승계 경로를 통째로 재설계하는 대신 승계값이 `None`이 되게 두고, 사용자는 정산 화면의
"코스트센터 (기본값)" 셀렉트에서 고른다. 그 UI는 이미 있고, 제출 시 `assert_centers_present`가
비어 있는 CC를 거부한다. 즉 검증 시점이 신청에서 정산 제출로 옮겨갈 뿐 빠지지 않는다.

출장 상세 화면은 값이 있을 때만 코스트센터를 렌더한다.

### DB 반영

`init-db`는 컬럼 변경을 반영하지 않고, `trip`은 `expense_report`가 참조하므로 테이블을 드롭하면
정산 데이터가 함께 사라진다. 수동 ALTER로 반영한다.

```sql
ALTER TABLE <schema>.trip
  DROP COLUMN transport_code,
  DROP COLUMN accommodation_code,
  DROP COLUMN estimated_cost;
ALTER TABLE <schema>.trip ALTER COLUMN cost_center_code DROP NOT NULL;
```

테스트 스키마는 매 세션 `drop_all`/`create_all`이므로 별도 조치가 필요 없다.

## 2. 정산 카드내역 피커

### 백엔드

`GET /api/v1/card-transactions`에 `unsettled: bool = False`를 추가한다. true면 어떤 정산서에도
담기지 않은 거래만 남긴다 — `expense_item.card_transaction_id`에 존재하는 id를 `NOT IN`
서브쿼리로 제외한다. 정산서 상태는 보지 않는다. 자동매칭이 이미 같은 기준으로 후보를 거르므로
규칙이 하나로 유지된다.

새 라우트가 아니므로 `SCOPE_REQUIREMENTS`는 그대로다. 소유자 필터는 기존 `list_card_transactions`가
이미 건다.

`CardTransactionOut`에 `suggested_expense_category_code`를 더한다. 값은
`services/matching.suggest_expense_category()`가 만든다. 프론트에서 업종→비목 매핑을 다시 짜면
자동매칭이 추천하는 비목과 피커가 추천하는 비목이 갈라진다.

### 프론트

이 프로젝트에 모달 패턴이 없으므로 `Modal.svelte`를 새로 만든다. `<dialog>` + `showModal()`을
쓴다 — SecureContext 전용 API가 아니므로 평문 HTTP 운영에서 동작한다. 제목·닫기·백드롭 클릭
닫기까지만 담는다.

`CardTransactionPicker.svelte`가 모달 본문이다. `unsettled=true`로 20건씩 조회하고, 가맹점
검색과 페이지 이동을 제공하며, 각 행의 `담기` 버튼이 부모의 콜백을 부른다.

정산 상세 화면의 "정산 항목" 헤더 옆에 `법인카드 사용내역 보기` 버튼을 둔다. 편집 가능한 상태
(DRAFT · REJECTED, 본인)에서만 보인다. 담기는 기존 `act()`를 지나므로 중복 제출 가드와 에러 표시를
그대로 쓴다. 담은 거래는 `unsettled` 필터에서 빠지므로 목록 새로고침 시 사라진다.

## 테스트

- `unsettled=true`가 담긴 거래를 제외하는지, 타인 거래를 노출하지 않는지.
- `suggested_expense_category_code`가 업종 매핑을 따르는지.
- 출장 생성·수정이 제거된 필드를 받지 않는지, 코스트센터 없이 생성되는지.
- 코스트센터 없는 출장의 정산서가 CC `None`으로 생기고, 그대로 제출하면 `CENTER_REQUIRED`로
  거부되는지.
- 프론트는 `npm run check` 0 errors / 0 warnings 유지.
