def _body(**overrides) -> dict:
    payload = {
        "title": "울산공장 품질점검",
        "purpose_code": "AUDIT",
        "purpose_detail": "라인 3 품질 이슈 현장 확인",
        "destination_type_code": "DOMESTIC",
        "country_code": "KR",
        "city": "울산",
        "start_date": "2026-09-01",
        "end_date": "2026-09-03",
        "transport_code": "RAIL",
        "accommodation_code": "HOTEL",
        "cost_center_code": "CC2030",
        "estimated_cost": "450000",
    }
    payload.update(overrides)
    return payload


async def test_list_requires_authentication(client, seeded):
    response = await client.get("/api/v1/trips")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_CREDENTIALS"


async def test_list_returns_my_trips_paged(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/trips", headers=headers, params={"size": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["size"] == 5
    assert body["total"] >= 1
    assert len(body["items"]) <= 5
    assert all(item["user_name"] for item in body["items"])


async def test_list_rejects_all_scope_for_employee(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/trips", headers=headers, params={"scope": "all"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_SCOPE"


async def test_list_allows_all_scope_for_admin(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/trips", headers=headers, params={"scope": "all"})

    assert response.status_code == 200
    assert response.json()["total"] == 40


async def test_list_accepts_repeated_status_params(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get(
        "/api/v1/trips", headers=headers, params=[("status", "APPROVED"), ("status", "COMPLETED")]
    )

    assert response.status_code == 200
    assert {item["status"] for item in response.json()["items"]} <= {"APPROVED", "COMPLETED"}


async def test_list_rejects_unknown_status_value(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/trips", headers=headers, params={"status": "NOPE"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SCHEMA_INVALID"


async def test_list_rejects_out_of_range_page_size(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/trips", headers=headers, params={"size": 500})

    assert response.status_code == 422


async def test_create_returns_201_with_draft(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.post("/api/v1/trips", headers=headers, json=_body())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["trip_no"].startswith("BT-")
    assert body["cost_center_name"]


async def test_create_rejects_invalid_code_with_field(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.post(
        "/api/v1/trips", headers=headers, json=_body(transport_code="ROCKET")
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "INVALID_CODE"
    assert error["field"] == "transport_code"


async def test_create_rejects_bad_date_range(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.post(
        "/api/v1/trips", headers=headers, json=_body(start_date="2026-09-05", end_date="2026-09-01")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"


async def test_create_rejects_overflowing_amount_as_400_not_500(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.post(
        "/api/v1/trips", headers=headers, json=_body(estimated_cost="99999999999999999999")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_AMOUNT"


async def test_get_detail_of_my_trip(client, seeded, login_as):
    headers = await login_as("user1@skon.example")
    created = await client.post("/api/v1/trips", headers=headers, json=_body())
    trip_id = created.json()["id"]

    response = await client.get(f"/api/v1/trips/{trip_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["purpose_detail"] == "라인 3 품질 이슈 현장 확인"


async def test_get_someone_elses_trip_is_404(client, seeded, login_as):
    mine = await login_as("user1@skon.example")
    created = await client.post("/api/v1/trips", headers=mine, json=_body())
    trip_id = created.json()["id"]
    theirs = await login_as("user2@skon.example")

    response = await client.get(f"/api/v1/trips/{trip_id}", headers=theirs)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRIP_NOT_FOUND"


async def test_patch_updates_a_draft(client, seeded, login_as):
    headers = await login_as("user1@skon.example")
    created = await client.post("/api/v1/trips", headers=headers, json=_body())
    trip_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/trips/{trip_id}", headers=headers, json={"city": "서산"}
    )

    assert response.status_code == 200
    assert response.json()["city"] == "서산"
    assert response.json()["title"] == "울산공장 품질점검"


async def test_delete_removes_a_draft(client, seeded, login_as):
    headers = await login_as("user1@skon.example")
    created = await client.post("/api/v1/trips", headers=headers, json=_body())
    trip_id = created.json()["id"]

    response = await client.delete(f"/api/v1/trips/{trip_id}", headers=headers)

    assert response.status_code == 204
    assert (await client.get(f"/api/v1/trips/{trip_id}", headers=headers)).status_code == 404
