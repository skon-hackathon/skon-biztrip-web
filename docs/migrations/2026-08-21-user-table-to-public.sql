-- user 테이블을 DB_SCHEMA(skon)에서 public으로 옮긴다.
--
-- 왜: 해커톤 데모에서 다른 프로젝트와 **계정을 공유**하기 위해서다. 원래는 SSO/auth 연계가
-- 맞지만 데모 범위에서는 같은 테이블 + 같은 JWT_SECRET으로 대신한다. 두 프로젝트가 같은
-- SECRET·HS256을 쓰면 payload {"sub": "<user.id>"} 토큰이 서로 통용된다.
--
-- 이 프로젝트는 Alembic을 쓰지 않는다. 이 파일은 **사람이 psql로 한 번 실행**한다.
-- app.cli init-db는 없는 테이블만 만들 뿐 기존 테이블의 스키마·컬럼 변경을 반영하지 않는다.
-- 코드만 배포하고 이걸 돌리지 않으면 앱이 존재하지 않는 public."user"를 찔러 500이 난다.
--
-- 실행:
--   psql "postgresql://<user>@<host>:<port>/<db>" -v ON_ERROR_STOP=1 \
--        -f docs/migrations/2026-08-21-user-table-to-public.sql
--
-- 주의: "user"는 PostgreSQL 예약어다. 따옴표 없이 쓰면 조용히 현재 역할명을 뜻한다.
-- 주의: 아래는 DB_SCHEMA=skon 기준이다. 다른 스키마를 쓴다면 `skon`을 전부 치환할 것.
--       psql의 \set 변수는 DO $$ ... $$ 안에서 치환되지 않으므로 일부러 리터럴로 적었다.

-- 0) 선행 확인 ---------------------------------------------------------------
-- public에 이미 user 테이블이 있으면(상대 프로젝트가 먼저 만들었다면) 이 스크립트를
-- 그대로 돌리면 안 된다. 그 경우 이 테이블을 옮기는 대신 우리 데이터를 그쪽에 넣어야 한다.
DO $$
BEGIN
    IF to_regclass('public."user"') IS NOT NULL THEN
        RAISE EXCEPTION 'public."user"가 이미 있습니다. 옮기지 말고 계정 병합 방법을 먼저 정하십시오.';
    END IF;
END $$;

BEGIN;

-- 1) department FK 제거 ------------------------------------------------------
-- public.user가 skon.department를 역참조하면, 계정을 공유하는 상대 프로젝트가 사용자를
-- 만들 때 우리 부서 행이 반드시 있어야 한다. 그 결합을 끊는다. 부서 존재 검증은 앱이 한다
-- (services/admin/users.py의 _assert_department). 부서 삭제 시 사용자 참조 검사도 앱이
-- 직접 센다 (services/admin/departments.py) — FK가 없어 DB가 막아주지 못하기 때문이다.
DO $$
DECLARE
    fk_name text;
BEGIN
    SELECT con.conname INTO fk_name
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
    WHERE nsp.nspname = 'skon'
      AND rel.relname = 'user'
      AND con.contype = 'f'
      AND pg_get_constraintdef(con.oid) LIKE '%(department_id)%';

    IF fk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE skon."user" DROP CONSTRAINT %I', fk_name);
    END IF;
END $$;

-- 2) role을 PG enum에서 varchar로 -------------------------------------------
-- 저장 문자열은 지금과 같다('EMPLOYEE'·'MANAGER'·'ADMIN'). 값 검증은 Python Enum이 한다.
-- enum 타입으로 두면 상대 프로젝트가 우리 스키마의 타입 이름에 묶인다.
ALTER TABLE skon."user" ALTER COLUMN role DROP DEFAULT;
ALTER TABLE skon."user" ALTER COLUMN role TYPE varchar(20) USING role::text;

-- 3) 테이블 이동 --------------------------------------------------------------
-- 이 테이블이 소유한 인덱스·유니크 제약·시퀀스(user_id_seq)는 함께 따라온다.
-- skon.trip·expense_report·api_key·activity_log·notification이 거는 FK는 이름이 아니라
-- OID로 대상을 잡으므로 끊기지 않는다 — 이동 후 스키마 간 FK가 될 뿐이다.
ALTER TABLE skon."user" SET SCHEMA public;

-- 4) 남은 enum 타입 정리 ------------------------------------------------------
-- 2번에서 마지막 사용처가 사라졌다. 아직 쓰는 곳이 있으면 DROP이 실패하고 트랜잭션이
-- 통째로 롤백된다 — 그게 옳은 동작이다.
DROP TYPE IF EXISTS skon.user_role;

COMMIT;

-- 5) 검증 ---------------------------------------------------------------------
-- 기대: 테이블은 public, 시퀀스도 public, role은 character varying,
--       user에 남은 FK는 자기참조(manager_id) 하나뿐.
SELECT table_schema, table_name FROM information_schema.tables WHERE table_name = 'user';
SELECT sequence_schema, sequence_name FROM information_schema.sequences WHERE sequence_name LIKE 'user_%';
SELECT column_name, data_type FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'user' AND column_name IN ('role', 'department_id');
SELECT con.conname, pg_get_constraintdef(con.oid)
  FROM pg_constraint con JOIN pg_class rel ON rel.oid = con.conrelid
  JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
 WHERE nsp.nspname = 'public' AND rel.relname = 'user' AND con.contype = 'f';
