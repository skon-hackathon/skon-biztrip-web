"""FC/CC Admin CRUD. 참조는 FK가 아니라 코드 문자열이므로 서비스가 직접 센다."""

import pytest


@pytest.mark.parametrize("kind", ["fund-centers", "cost-centers"])
async def test_employee_cannot_read_admin_centers(client, seeded, login_as, kind):
    headers = await login_as("user1@skon.example")

    assert (await client.get(f"/api/v1/admin/{kind}", headers=headers)).status_code == 403


@pytest.mark.parametrize("kind", ["fund-centers", "cost-centers"])
async def test_admin_creates_and_lists_a_center(client, seeded, login_as, kind):
    headers = await login_as("admin@skon.example")

    created = await client.post(
        f"/api/v1/admin/{kind}",
        headers=headers,
        json={"code": "ZZ9999", "name": "테스트센터", "department_id": None},
    )

    assert created.status_code == 201
    listed = (await client.get(f"/api/v1/admin/{kind}", headers=headers)).json()
    assert "ZZ9999" in [row["code"] for row in listed]


async def test_admin_list_includes_inactive_centers(client, seeded, login_as):
    """/api/v1/cost-centers는 활성만 준다. 관리 목록은 비활성도 보여야 한다."""
    headers = await login_as("admin@skon.example")
    created = (
        await client.post(
            "/api/v1/admin/cost-centers",
            headers=headers,
            json={"code": "CC9998", "name": "비활성센터", "is_active": False},
        )
    ).json()

    admin_list = (await client.get("/api/v1/admin/cost-centers", headers=headers)).json()
    public_list = (await client.get("/api/v1/cost-centers", headers=headers)).json()

    assert created["id"] in [row["id"] for row in admin_list]
    assert "CC9998" not in [row["code"] for row in public_list]


async def test_duplicate_center_code_is_409(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.post(
        "/api/v1/admin/cost-centers", headers=headers, json={"code": "CC2100", "name": "중복"}
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "DUPLICATE_CENTER_CODE"
    assert body["field"] == "code"


async def test_unknown_department_is_400(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.post(
        "/api/v1/admin/fund-centers",
        headers=headers,
        json={"code": "FC9999", "name": "고아센터", "department_id": 999999},
    )

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "INVALID_DEPARTMENT"
    assert body["field"] == "department_id"


async def test_referenced_cost_center_cannot_be_deleted(client, seeded, login_as):
    """시드의 출장들이 CC2100을 쓴다. FK가 없으므로 서비스가 세지 않으면 조용히 지워진다."""
    headers = await login_as("admin@skon.example")
    centers = (await client.get("/api/v1/admin/cost-centers", headers=headers)).json()
    target = next(row for row in centers if row["code"] == "CC2100")

    response = await client.delete(
        f"/api/v1/admin/cost-centers/{target['id']}", headers=headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HAS_DEPENDENTS"


async def test_unreferenced_center_can_be_deleted(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    created = (
        await client.post(
            "/api/v1/admin/cost-centers", headers=headers, json={"code": "CC9997", "name": "임시"}
        )
    ).json()

    response = await client.delete(
        f"/api/v1/admin/cost-centers/{created['id']}", headers=headers
    )

    assert response.status_code == 204


async def test_deactivating_a_center_blocks_new_trips(client, seeded, login_as):
    """마스터를 끄면 그 값으로는 새 쓰기가 통과하지 못해야 한다."""
    headers = await login_as("admin@skon.example")
    # 출장 생성은 신청자 계정으로 한다 — admin은 manager_id가 없어 결재자 규칙에 걸릴 수 있다.
    author_headers = await login_as("user1@skon.example")
    centers = (await client.get("/api/v1/admin/cost-centers", headers=headers)).json()
    target = next(row for row in centers if row["code"] == "CC2100")

    await client.patch(
        f"/api/v1/admin/cost-centers/{target['id']}", headers=headers, json={"is_active": False}
    )

    response = await client.post(
        "/api/v1/trips",
        headers=author_headers,
        json={
            "title": "비활성 센터",
            "purpose_code": "CUSTOMER",
            "purpose_detail": "점검",
            "destination_type_code": "DOMESTIC",
            "country_code": "KR",
            "city": "울산",
            "start_date": "2026-09-01",
            "end_date": "2026-09-02",
            "transport_code": "AIR",
            "accommodation_code": "HOTEL",
            "cost_center_code": "CC2100",
            "estimated_cost": "300000",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_COST_CENTER"


async def test_missing_center_is_404(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.patch(
        "/api/v1/admin/fund-centers/999999", headers=headers, json={"name": "없음"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CENTER_NOT_FOUND"
