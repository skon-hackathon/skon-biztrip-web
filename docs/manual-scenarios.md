# 브라우저 수동 시나리오

- 실행 방법: `docker compose -p skon-prod up -d --build` 후 `http://localhost` (평문 HTTP — SecureContext가 아니다)
- 계정: `admin@skon.example` · `manager1@skon.example` · `user1@skon.example` / 비밀번호 `skon1234!`
- 각 항목 앞의 체크박스는 **직접 눌러 본 뒤에만** 채운다. 못 돌렸으면 비워 두고 `docs/phase-status.md`에 미확인으로 남긴다.

## Phase 2 이월 (8)

- [ ] 로그인 전 `/trips/3` 딥링크 → 로그인 후 그 화면으로 복귀
- [ ] 출장 신청 폼에서 제출 버튼 연타 → 출장이 1건만 생성
- [ ] 반려된 출장에서 재작성(reopen) → DRAFT로 돌아오고 수정 가능
- [ ] 토큰 만료 상태로 목록 진입 → 로그인 화면으로 정리 (전역 401)
- [ ] 결재함이 MANAGER·ADMIN에게만 보인다
- [ ] 알림 벨 뱃지 숫자가 라우트 이동 후 갱신
- [ ] 목록 필터(상태·국가·기간·검색)가 URL과 함께 동작
- [ ] 타임라인이 CREATED·SUBMITTED·APPROVED 순으로 표시

## Phase 3 이월 (6)

- [ ] `/cards` 카드·기간·업종·검색 필터
- [ ] 정산서 생성 시 출장의 cost_center_code 승계
- [ ] 매칭 후보 "담기" → 항목 테이블에 추가되고 합계 갱신
- [ ] 항목의 부서 지정(상속 ↔ override) 토글
- [ ] FC 없이 제출 → 400 `CENTER_REQUIRED` 메시지 노출
- [ ] 정산 승인 후 출장이 SETTLED로 표시

## Phase 4 이월 (9)

- [ ] `/settings/api-keys` 렌더 (Phase 4에서 렌더 확인이 전혀 안 됐다)
- [ ] 키 발급 흐름 → 평문 1회 노출
- [ ] 복사 버튼 (평문 HTTP라 `navigator.clipboard`가 없다 — `execCommand` 폴백 확인)
- [ ] 발급 폼 연타 → 키 1개만 생성
- [ ] 스코프 미선택 시 발급 버튼 비활성
- [ ] 폐기 2단계 확인 → 목록 상태가 REVOKED
- [ ] `/developers` 렌더 + 스코프 표가 `GET /scopes` 응답과 일치
- [ ] 헤더 탭 활성 표시
- [ ] 전역 401 처리

## Phase 5 신규 (10)

- [ ] `/admin/codes` 그룹 생성 → 코드 추가 → 중지 → 삭제(2단계) 동작
- [ ] 활성 코드 삭제 시 409 메시지가 화면에 보인다
- [ ] `/admin/centers` FC/CC 탭 전환 시 목록이 바뀐다
- [ ] 참조 중인 센터 삭제 → 409 메시지
- [ ] `/admin/departments` 사용자 있는 부서 삭제 → 409 메시지
- [ ] `/admin/users` 검색 → 역할 변경 → 비활성화 (자기 자신은 비활성화 버튼이 disabled)
- [ ] `/admin/users` 비밀번호 재설정 후 그 계정으로 로그인
- [ ] `/admin/cards` 거래 있는 카드 삭제 → 409 메시지
- [ ] EMPLOYEE 계정으로 `/admin/codes` 직접 진입 → 대시보드로 돌아간다
- [ ] 375px에서 햄버거 시트 열림 → 링크 이동 후 자동 닫힘, 가로 스크롤 없음
