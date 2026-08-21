-- public."user"에 가입 상태 컬럼을 더하고, 가입 시점에 알 수 없는 두 컬럼의 NOT NULL을 푼다.
--
-- 왜: 회원가입을 열되 승인은 관리자가 하기 때문이다. 가입자는 이메일·이름·비밀번호·부서만
-- 내고, 사번·직급·결재자·역할은 관리자가 승인 시점에 채운다. 그 값들은 결재선과 정산 귀속의
-- 근거라 본인이 고르면 틀린다.
--
-- 설계: docs/superpowers/specs/2026-08-22-signup-approval-design.md
--
-- 선행: docs/migrations/2026-08-21-user-table-to-public.sql이 먼저 실행되어 있어야 한다.
--       (2026-08-22 실행 완료. user 테이블은 public에 있다.)
--
-- 이 프로젝트는 Alembic을 쓰지 않는다. 이 파일은 **사람이 psql로 한 번 실행**한다.
-- app.cli init-db는 없는 테이블만 만들 뿐 기존 테이블의 컬럼 변경을 반영하지 않는다.
-- 코드만 배포하고 이걸 돌리지 않으면 status 컬럼이 없어 로그인부터 500이 난다.
--
-- 실행:
--   psql "postgresql://<user>@<host>:<port>/<db>" -v ON_ERROR_STOP=1 \
--        -f docs/migrations/2026-08-22-user-signup-status.sql
--
-- 주의: "user"는 PostgreSQL 예약어다. 따옴표 없이 쓰면 조용히 현재 역할명을 뜻한다.

-- 0) 선행 확인 ---------------------------------------------------------------
DO $$
BEGIN
    IF to_regclass('public."user"') IS NULL THEN
        RAISE EXCEPTION 'public."user"가 없습니다. 2026-08-21 이관 SQL을 먼저 실행하십시오.';
    END IF;
END $$;

BEGIN;

-- 1) status 컬럼 -------------------------------------------------------------
-- DEFAULT 'ACTIVE'이므로 기존 행은 전부 ACTIVE가 된다. 그게 옳다 — 지금 있는 계정은
-- 모두 관리자가 만들었거나 시드로 들어온 승인된 계정이다.
-- PG enum 타입을 만들지 않는 이유는 role과 같다. 계정을 공유하는 상대 프로젝트가
-- 우리 스키마의 타입 이름에 묶이는 결합을 만들지 않는다.
ALTER TABLE public."user"
    ADD COLUMN IF NOT EXISTS status varchar(20) NOT NULL DEFAULT 'ACTIVE';

-- 2) 가입 시점에 알 수 없는 두 컬럼의 NOT NULL 해제 ---------------------------
-- 임시값(예: 'PENDING-<uuid>')을 넣지 않는 이유: 그 가짜 사번이 상대 프로젝트·유저 관리
-- 화면·Agent API에 실제 사번처럼 노출된다. NULL은 "없다"를 정직하게 말한다.
-- employee_no의 unique 제약은 유지한다 — Postgres에서 NULL끼리는 충돌하지 않는다.
ALTER TABLE public."user" ALTER COLUMN employee_no DROP NOT NULL;
ALTER TABLE public."user" ALTER COLUMN position_code DROP NOT NULL;

COMMIT;

-- 3) 검증 ---------------------------------------------------------------------
-- 기대: status는 character varying NOT NULL, 나머지 둘은 is_nullable = YES.
--       기존 계정은 전부 ACTIVE.
SELECT column_name, data_type, is_nullable, column_default
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'user'
   AND column_name IN ('status', 'employee_no', 'position_code')
 ORDER BY column_name;

SELECT status, count(*) FROM public."user" GROUP BY status;
