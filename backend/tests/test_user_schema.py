"""`user` 테이블만 다른 스키마에 산다 — 계정을 다른 프로젝트와 공유하기 때문이다.

여기 테스트들이 지키는 것은 두 가지다. (1) 테스트 세션이 공유 계정 테이블을 건드리지
않는다는 것, (2) 공유 테이블이 이 프로젝트 스키마를 역참조하지 않는다는 것. 둘 중 하나가
깨지면 조용히 깨진다 — 앱은 멀쩡히 뜨고 테스트만 남의 데이터를 지운다.
"""

from app.config import Settings
from app.models import ApiKey, Base, Trip, User
from tests.conftest import TEST_SCHEMA


def test_user_table_lives_in_the_test_schema_during_tests():
    """conftest가 USER_DB_SCHEMA를 덮어쓰지 못하면 drop_all이 공유 계정을 지운다."""
    assert User.__table__.schema == TEST_SCHEMA


def test_no_table_points_at_public_during_tests():
    """metadata 전체가 테스트 스키마 안이거나 스키마 미지정(search_path)이어야 한다."""
    schemas = {table.schema for table in Base.metadata.tables.values()}
    assert schemas <= {None, TEST_SCHEMA}


def test_user_defaults_to_public_schema(monkeypatch):
    """기본값이 public이라야 운영에서 다른 프로젝트와 같은 테이블을 본다.

    conftest가 테스트 세션 전체에 USER_DB_SCHEMA를 걸어두므로 여기서만 걷어낸다.
    """
    monkeypatch.delenv("USER_DB_SCHEMA", raising=False)
    assert Settings(_env_file=None).user_db_schema == "public"


def test_user_has_no_foreign_key_into_this_projects_schema():
    """공유 테이블이 우리 스키마를 참조하면 상대 프로젝트가 계정을 못 만든다.

    남아도 되는 FK는 user -> user(manager_id) 자기참조뿐이다.
    """
    targets = {fk.target_fullname for fk in User.__table__.foreign_keys}
    assert targets == {f"{TEST_SCHEMA}.user.id"}
    assert "department_id" not in {fk.parent.name for fk in User.__table__.foreign_keys}


def test_our_tables_still_reference_the_shared_user_table():
    """반대 방향은 유지한다 — 우리 데이터가 없는 계정을 가리키면 안 된다."""
    for table in (Trip.__table__, ApiKey.__table__):
        targets = {fk.target_fullname for fk in table.foreign_keys}
        assert f"{TEST_SCHEMA}.user.id" in targets


def test_role_is_stored_as_a_string_not_a_postgres_enum():
    """PG enum 타입이면 상대 프로젝트가 우리 스키마의 타입에 묶인다."""
    role_type = User.__table__.c.role.type
    assert role_type.native_enum is False
    assert role_type.length >= 20
