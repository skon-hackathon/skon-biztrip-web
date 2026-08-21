"""사용자 Admin CRUD.

삭제는 없다(비활성화만). 비밀번호 설정은 JWT 전용이다 — admin 스코프 키로 남의 비밀번호를
바꿀 수 있으면 그 계정으로 로그인해 전권 키를 발급할 수 있고, 키 관리 API를 JWT 전용으로
막아둔 이유가 통째로 우회된다.
"""

import pytest
from sqlalchemy import event, select

from app.enums import ApiKeyScope
from app.models import User
from tests.factories import make_api_key, make_user


@pytest.fixture
def count_statements(test_engine):
    """실행된 SQL 문 수를 센다. 행 수에 비례해 늘어나면 N+1이다."""
    counter = {"n": 0}

    def before(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    event.listen(test_engine.sync_engine, "before_cursor_execute", before)
    yield counter
    event.remove(test_engine.sync_engine, "before_cursor_execute", before)


async def test_employee_cannot_list_users(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    assert (await client.get("/api/v1/admin/users", headers=headers)).status_code == 403


async def test_admin_lists_users_with_names_resolved(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/admin/users?size=100", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 14
    user1 = next(row for row in body["items"] if row["email"] == "user1@skon.example")
    assert user1["department_name"]
    assert user1["manager_name"] == "김연구"


async def test_user_list_query_count_does_not_grow_with_rows(
    client, seeded, login_as, count_statements
):
    headers = await login_as("admin@skon.example")
    await client.get("/api/v1/admin/users?size=5", headers=headers)  # 워밍업

    # 두 표본 모두 결재자가 있는 사용자를 포함해야 한다. size=1은 결재자 없는 admin 한 명만
    # 잡혀 결재자 조회가 통째로 생략되고, 그 차이가 N+1로 오독된다.
    start = count_statements["n"]
    await client.get("/api/v1/admin/users?size=5", headers=headers)
    few_rows = count_statements["n"] - start

    start = count_statements["n"]
    await client.get("/api/v1/admin/users?size=100", headers=headers)
    many_rows = count_statements["n"] - start

    assert few_rows == many_rows
    # 등가 비교만으로는 "행마다"가 아니라 "고유 결재자마다" 조회하는 변형을 놓친다
    # (시드의 결재자는 3명뿐이라 표본 크기와 무관하게 같은 수가 나온다).
    # 절대 상한이 그 구멍을 막는다: 인증 1 + count 1 + 목록 1 + 부서 1 + 결재자 1 = 5.
    # (결재자를 행별 session.get으로 바꾸면 목록 쿼리가 이미 적재한 identity map에서 나와
    #  SQL이 늘지 않는다. 실제로 늘어나는 것은 부서 조회이고, 이 상한이 그것을 잡는다.)
    assert many_rows <= 5


async def test_user_search_matches_name_email_and_employee_no(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    for term in ("김연구", "manager1@skon.example", "E0002"):
        response = await client.get(f"/api/v1/admin/users?q={term}", headers=headers)
        emails = [row["email"] for row in response.json()["items"]]
        assert "manager1@skon.example" in emails, term


async def test_admin_creates_a_user_who_can_log_in(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    departments = (await client.get("/api/v1/admin/departments", headers=headers)).json()

    created = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "new.hire@skon.example",
            "password": "skon1234!",
            "name": "신입사원",
            "employee_no": "E9001",
            "department_id": departments[0]["id"],
            "position_code": "STAFF",
        },
    )

    assert created.status_code == 201
    assert created.json()["role"] == "EMPLOYEE"
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "new.hire@skon.example", "password": "skon1234!"},
    )
    assert login.status_code == 200


async def test_duplicate_email_is_409(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    departments = (await client.get("/api/v1/admin/departments", headers=headers)).json()

    response = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "user1@skon.example",
            "password": "skon1234!",
            "name": "중복",
            "employee_no": "E9002",
            "department_id": departments[0]["id"],
            "position_code": "STAFF",
        },
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "DUPLICATE_EMAIL"
    assert body["field"] == "email"


async def test_unknown_position_code_is_400(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    departments = (await client.get("/api/v1/admin/departments", headers=headers)).json()

    response = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "bad.position@skon.example",
            "password": "skon1234!",
            "name": "잘못된직급",
            "employee_no": "E9003",
            "department_id": departments[0]["id"],
            "position_code": "NOT_A_POSITION",
        },
    )

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "INVALID_CODE"
    assert body["field"] == "position_code"


async def test_short_password_is_400_not_422(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    departments = (await client.get("/api/v1/admin/departments", headers=headers)).json()

    response = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "short.pw@skon.example",
            "password": "abc",
            "name": "짧은비번",
            "employee_no": "E9004",
            "department_id": departments[0]["id"],
            "position_code": "STAFF",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PASSWORD_TOO_SHORT"


async def test_korean_password_over_72_bytes_is_400_not_500(client, seeded, login_as):
    """bcrypt 5.x는 72바이트 초과를 자르지 않고 던진다 — 막지 않으면 500이고 Agent가 재시도한다."""
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
    target = next(row for row in users["items"] if row["email"] == "user1@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{target['id']}/password",
        headers=headers,
        json={"password": "가" * 25},
    )

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "PASSWORD_TOO_LONG"
    assert body["field"] == "password"


async def test_password_reset_changes_the_login(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
    target = next(row for row in users["items"] if row["email"] == "user2@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{target['id']}/password",
        headers=headers,
        json={"password": "새비밀번호1234"},
    )

    assert response.status_code == 204
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "user2@skon.example", "password": "새비밀번호1234"},
    )
    assert login.status_code == 200


async def test_password_reset_rejects_api_keys(client, seeded, db_session, login_as):
    """admin 스코프 키가 비밀번호를 바꿀 수 있으면 키가 JWT로 승격되는 길이 열린다."""
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
    target = next(row for row in users["items"] if row["email"] == "user3@skon.example")

    admin = (
        await db_session.execute(select(User).where(User.email == "admin@skon.example"))
    ).scalar_one()
    raw, _ = await make_api_key(db_session, user=admin, scopes=[ApiKeyScope.ADMIN])
    await db_session.commit()

    response = await client.post(
        f"/api/v1/admin/users/{target['id']}/password",
        headers={"X-API-Key": raw},
        json={"password": "키로바꾸기1234"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "API_KEY_FORBIDDEN"


async def test_admin_cannot_demote_self(client, seeded, login_as):
    """마지막 ADMIN이 스스로를 강등하면 복구 경로가 DB 직접 수정뿐이 된다."""
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
    me = next(row for row in users["items"] if row["email"] == "admin@skon.example")

    response = await client.patch(
        f"/api/v1/admin/users/{me['id']}", headers=headers, json={"role": "EMPLOYEE"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CANNOT_DEMOTE_SELF"


async def test_admin_cannot_deactivate_self(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
    me = next(row for row in users["items"] if row["email"] == "admin@skon.example")

    response = await client.patch(
        f"/api/v1/admin/users/{me['id']}", headers=headers, json={"is_active": False}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CANNOT_DEMOTE_SELF"


async def test_deactivated_user_cannot_log_in(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
    target = next(row for row in users["items"] if row["email"] == "user4@skon.example")

    await client.patch(
        f"/api/v1/admin/users/{target['id']}", headers=headers, json={"is_active": False}
    )

    login = await client.post(
        "/api/v1/auth/login", json={"email": "user4@skon.example", "password": "skon1234!"}
    )
    assert login.status_code == 401


async def test_manager_cannot_point_at_itself(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    victim = await make_user(db_session, name="자기결재")
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/admin/users/{victim.id}", headers=headers, json={"manager_id": victim.id}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MANAGER"


async def test_get_single_user_is_404_when_missing(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/admin/users/999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


async def _pending(db_session):
    from app.enums import UserStatus
    from tests.factories import make_user

    user = await make_user(db_session, status=UserStatus.PENDING, is_active=False)
    user.employee_no = None
    user.position_code = None
    await db_session.commit()
    return user


async def test_approve_fills_org_fields_and_opens_login(client, db_session, seeded, login_as):
    from app.enums import UserStatus

    user = await _pending(db_session)
    headers = await login_as("admin@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{user.id}/approve",
        json={"employee_no": "E0777", "position_code": "STAFF", "role": "EMPLOYEE"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["employee_no"] == "E0777"
    assert body["is_active"] is True

    await db_session.refresh(user)
    assert user.status is UserStatus.ACTIVE
    assert user.is_active is True


async def test_approve_rejects_duplicate_employee_no(client, db_session, seeded, login_as):
    user = await _pending(db_session)
    headers = await login_as("admin@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{user.id}/approve",
        json={"employee_no": "E0001", "position_code": "STAFF"},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_EMPLOYEE_NO"


async def test_approve_rejects_unknown_position(client, db_session, seeded, login_as):
    user = await _pending(db_session)
    headers = await login_as("admin@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{user.id}/approve",
        json={"employee_no": "E0778", "position_code": "NOT_A_CODE"},
        headers=headers,
    )
    assert response.status_code == 400


async def test_approve_twice_conflicts(client, db_session, seeded, login_as):
    user = await _pending(db_session)
    headers = await login_as("admin@skon.example")
    body = {"employee_no": "E0779", "position_code": "STAFF"}

    first = await client.post(
        f"/api/v1/admin/users/{user.id}/approve", json=body, headers=headers
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/admin/users/{user.id}/approve",
        json={"employee_no": "E0780", "position_code": "STAFF"},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "USER_INVALID_TRANSITION"


async def test_reject_closes_account(client, db_session, seeded, login_as):
    from app.enums import UserStatus

    user = await _pending(db_session)
    headers = await login_as("admin@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{user.id}/reject", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"

    await db_session.refresh(user)
    assert user.status is UserStatus.REJECTED
    assert user.is_active is False


async def test_reject_active_user_conflicts(client, db_session, seeded, login_as):
    from tests.factories import make_user

    user = await make_user(db_session)
    await db_session.commit()
    headers = await login_as("admin@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{user.id}/reject", headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USER_INVALID_TRANSITION"


async def test_list_users_filters_by_status(client, db_session, seeded, login_as):
    await _pending(db_session)
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/admin/users?status=PENDING", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    assert all(item["status"] == "PENDING" for item in items)


async def test_patch_cannot_change_status(client, db_session, seeded, login_as):
    """status는 전이 엔드포인트만 바꾼다. PATCH로 열리면 전이 가드 우회 경로가 생긴다."""
    from app.enums import UserStatus

    user = await _pending(db_session)
    headers = await login_as("admin@skon.example")

    response = await client.patch(
        f"/api/v1/admin/users/{user.id}", json={"status": "ACTIVE"}, headers=headers
    )
    # Pydantic이 모르는 필드를 무시하든 거부하든, 상태는 바뀌지 않아야 한다.
    await db_session.refresh(user)
    assert user.status is UserStatus.PENDING
    assert response.status_code in (200, 422)
