"""부서 Admin CRUD. 역할 검사 + 참조 삭제 변환이 핵심이다."""

from app.enums import UserRole
from tests.factories import make_department, make_user


async def test_employee_cannot_list_departments(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/admin/departments", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_manager_cannot_list_departments(client, seeded, login_as):
    headers = await login_as("manager1@skon.example")

    assert (await client.get("/api/v1/admin/departments", headers=headers)).status_code == 403


async def test_admin_lists_departments_in_code_order(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/admin/departments", headers=headers)

    assert response.status_code == 200
    codes = [row["code"] for row in response.json()]
    assert codes == sorted(codes)
    assert "D100" in codes


async def test_admin_creates_a_department(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.post(
        "/api/v1/admin/departments",
        headers=headers,
        json={"code": "D900", "name": "신규팀", "parent_id": None},
    )

    assert response.status_code == 201
    assert response.json()["code"] == "D900"
    listed = await client.get("/api/v1/admin/departments", headers=headers)
    assert "D900" in [row["code"] for row in listed.json()]


async def test_duplicate_department_code_is_409_with_a_field(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.post(
        "/api/v1/admin/departments", headers=headers, json={"code": "D100", "name": "중복"}
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "DUPLICATE_DEPARTMENT_CODE"
    assert body["field"] == "code"


async def test_unknown_parent_is_400(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.post(
        "/api/v1/admin/departments",
        headers=headers,
        json={"code": "D901", "name": "고아", "parent_id": 999999},
    )

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "INVALID_PARENT"
    assert body["field"] == "parent_id"


async def test_department_cannot_be_its_own_parent(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    department = await make_department(db_session, name="자기참조")
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/admin/departments/{department.id}",
        headers=headers,
        json={"parent_id": department.id},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARENT"


async def test_patch_only_changes_sent_fields(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    parent = await make_department(db_session, name="상위")
    child = await make_department(db_session, name="하위")
    child.parent_id = parent.id
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/admin/departments/{child.id}", headers=headers, json={"name": "이름만변경"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "이름만변경"
    # parent_id를 보내지 않았으므로 그대로여야 한다. exclude_unset이 없으면 null로 지워진다.
    assert body["parent_id"] == parent.id


async def test_explicit_null_clears_the_parent(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    parent = await make_department(db_session, name="상위2")
    child = await make_department(db_session, name="하위2")
    child.parent_id = parent.id
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/admin/departments/{child.id}", headers=headers, json={"parent_id": None}
    )

    assert response.status_code == 200
    assert response.json()["parent_id"] is None


async def test_deleting_a_referenced_department_is_409(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    department = await make_department(db_session, name="사람있는부서")
    await make_user(db_session, department=department, role=UserRole.EMPLOYEE)
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/admin/departments/{department.id}", headers=headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HAS_DEPENDENTS"


async def test_deleting_an_empty_department_succeeds(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    department = await make_department(db_session, name="빈부서")
    department_id = department.id
    await db_session.commit()

    response = await client.delete(f"/api/v1/admin/departments/{department_id}", headers=headers)

    assert response.status_code == 204
    listed = await client.get("/api/v1/admin/departments", headers=headers)
    assert department_id not in [row["id"] for row in listed.json()]


async def test_missing_department_is_404(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.patch(
        "/api/v1/admin/departments/999999", headers=headers, json={"name": "없음"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DEPARTMENT_NOT_FOUND"
