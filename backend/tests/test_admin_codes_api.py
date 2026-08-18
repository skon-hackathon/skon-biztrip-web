"""공통코드 Admin CRUD.

업무 테이블이 코드값을 문자열로 들고 있어 FK가 없다 — DB가 막아주지 않으므로
"비활성화 후 삭제" 2단계를 서비스가 강제한다.
"""


async def _admin(login_as):
    return await login_as("admin@skon.example")


async def test_employee_cannot_read_admin_code_groups(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    assert (await client.get("/api/v1/admin/code-groups", headers=headers)).status_code == 403


async def test_admin_list_includes_inactive_codes(client, seeded, login_as):
    """관리 화면은 비활성 코드를 봐야 되살릴 수 있다. /api/v1/codes와 다른 점이다."""
    headers = await _admin(login_as)
    groups = (await client.get("/api/v1/admin/code-groups", headers=headers)).json()
    transport = next(g for g in groups if g["group_code"] == "TRANSPORT")
    code_id = transport["codes"][0]["id"]

    await client.patch(
        f"/api/v1/admin/codes/{code_id}", headers=headers, json={"is_active": False}
    )

    admin_groups = (await client.get("/api/v1/admin/code-groups", headers=headers)).json()
    admin_transport = next(g for g in admin_groups if g["group_code"] == "TRANSPORT")
    assert code_id in [c["id"] for c in admin_transport["codes"]]

    public = (await client.get("/api/v1/codes/TRANSPORT", headers=headers)).json()
    assert transport["codes"][0]["code"] not in [c["code"] for c in public["codes"]]


async def test_admin_creates_a_group_and_a_code(client, seeded, login_as):
    headers = await _admin(login_as)

    group = await client.post(
        "/api/v1/admin/code-groups",
        headers=headers,
        json={"group_code": "RISK_LEVEL", "name": "위험도"},
    )
    assert group.status_code == 201
    group_id = group.json()["id"]

    code = await client.post(
        f"/api/v1/admin/code-groups/{group_id}/codes",
        headers=headers,
        json={"code": "HIGH", "name": "높음", "sort_order": 1, "extra": {"color": "red"}},
    )

    assert code.status_code == 201
    assert code.json()["extra"] == {"color": "red"}


async def test_duplicate_group_code_is_409(client, seeded, login_as):
    headers = await _admin(login_as)

    response = await client.post(
        "/api/v1/admin/code-groups",
        headers=headers,
        json={"group_code": "TRANSPORT", "name": "중복"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_CODE_GROUP"


async def test_duplicate_code_within_a_group_is_409(client, seeded, login_as):
    headers = await _admin(login_as)
    groups = (await client.get("/api/v1/admin/code-groups", headers=headers)).json()
    transport = next(g for g in groups if g["group_code"] == "TRANSPORT")

    response = await client.post(
        f"/api/v1/admin/code-groups/{transport['id']}/codes",
        headers=headers,
        json={"code": transport["codes"][0]["code"], "name": "중복"},
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "DUPLICATE_CODE"
    assert body["field"] == "code"


async def test_active_code_cannot_be_deleted(client, seeded, login_as):
    """활성 코드를 지우면 그 값을 쓰는 출장·정산 행이 고아가 된다. 2단계를 강제한다."""
    headers = await _admin(login_as)
    groups = (await client.get("/api/v1/admin/code-groups", headers=headers)).json()
    code_id = next(g for g in groups if g["group_code"] == "TRANSPORT")["codes"][0]["id"]

    response = await client.delete(f"/api/v1/admin/codes/{code_id}", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CODE_STILL_ACTIVE"


async def test_inactive_code_can_be_deleted(client, seeded, login_as):
    headers = await _admin(login_as)
    group = (
        await client.post(
            "/api/v1/admin/code-groups",
            headers=headers,
            json={"group_code": "TEMP_GROUP", "name": "임시"},
        )
    ).json()
    code = (
        await client.post(
            f"/api/v1/admin/code-groups/{group['id']}/codes",
            headers=headers,
            json={"code": "TMP", "name": "임시코드", "is_active": False},
        )
    ).json()

    response = await client.delete(f"/api/v1/admin/codes/{code['id']}", headers=headers)

    assert response.status_code == 204


async def test_group_with_codes_cannot_be_deleted(client, seeded, login_as):
    """cascade="all, delete-orphan"이 자식을 조용히 쓸어가는 것을 막는다."""
    headers = await _admin(login_as)
    groups = (await client.get("/api/v1/admin/code-groups", headers=headers)).json()
    transport = next(g for g in groups if g["group_code"] == "TRANSPORT")

    response = await client.delete(
        f"/api/v1/admin/code-groups/{transport['id']}", headers=headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HAS_DEPENDENTS"


async def test_empty_group_can_be_deleted(client, seeded, login_as):
    headers = await _admin(login_as)
    group = (
        await client.post(
            "/api/v1/admin/code-groups",
            headers=headers,
            json={"group_code": "EMPTY_GROUP", "name": "빈그룹"},
        )
    ).json()

    response = await client.delete(f"/api/v1/admin/code-groups/{group['id']}", headers=headers)

    assert response.status_code == 204


async def test_deactivating_a_group_hides_it_from_the_public_endpoint(client, seeded, login_as):
    headers = await _admin(login_as)
    groups = (await client.get("/api/v1/admin/code-groups", headers=headers)).json()
    accommodation = next(g for g in groups if g["group_code"] == "ACCOMMODATION")

    await client.patch(
        f"/api/v1/admin/code-groups/{accommodation['id']}",
        headers=headers,
        json={"is_active": False},
    )

    public = await client.get("/api/v1/codes/ACCOMMODATION", headers=headers)
    assert public.status_code == 404


async def test_missing_group_is_404(client, seeded, login_as):
    headers = await _admin(login_as)

    response = await client.post(
        "/api/v1/admin/code-groups/999999/codes",
        headers=headers,
        json={"code": "X", "name": "없는그룹"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CODE_GROUP_NOT_FOUND"
