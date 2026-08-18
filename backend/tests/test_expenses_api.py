"""정산 API 계약. 시드 데이터 + JWT로 사람이 하는 순서를 그대로 밟는다.

같은 엔드포인트를 Agent가 쓰는 것이 이 프로젝트의 핵심 메시지이므로, 에러 바디의
code·field까지 단언한다.
"""

from app.enums import TripStatus


async def _owner_with_settleable_trip(client, login_as):
    """정산서가 아직 없는 COMPLETED 출장과 그 소유자·결재자를 시드에서 찾는다.

    시드는 완료/정산 출장 17건 중 앞의 12건에만 정산서를 만들어 두므로, 어느 사원에게
    남는 출장이 있는지는 시드 난수에 달려 있다. 특정 계정을 하드코딩하면 시드가 조금만
    바뀌어도 테스트가 깨진다 — 그래서 사원들을 훑는다.

    결재자는 `_seed_users`의 배정 규칙(employees[index] → managers[index % 3])을 따른다.
    """
    for index in range(10):
        headers = await login_as(f"user{index + 1}@skon.example")
        trips = (
            await client.get("/api/v1/trips?status=COMPLETED&size=50", headers=headers)
        ).json()
        expenses = (await client.get("/api/v1/expenses?size=100", headers=headers)).json()
        taken = {item["trip_id"] for item in expenses["items"]}
        for trip in trips["items"]:
            if trip["id"] not in taken:
                return headers, trip, f"manager{index % 3 + 1}@skon.example"
    raise AssertionError("정산서가 없는 COMPLETED 출장이 시드에 없습니다")


async def _stranger_headers(client, login_as, trip):
    """신청자도 결재자도 아닌 사원의 헤더. 계정을 하드코딩하면 시드 난수에 따라
    우연히 본인/결재자를 고를 수 있다."""
    for index in range(10):
        headers = await login_as(f"user{index + 1}@skon.example")
        me = (await client.get("/api/v1/auth/me", headers=headers)).json()
        if me["id"] not in {trip["user_id"], trip["approver_id"]}:
            return headers
    raise AssertionError("제3자로 쓸 사원 계정을 찾지 못했습니다")


async def test_full_expense_flow_over_http(client, login_as, seeded):
    owner_headers, trip, approver_email = await _owner_with_settleable_trip(client, login_as)

    created = await client.post(
        "/api/v1/expenses", json={"trip_id": trip["id"]}, headers=owner_headers
    )
    assert created.status_code == 201, created.text
    report = created.json()
    assert report["status"] == "DRAFT"
    trip_detail = (await client.get(f"/api/v1/trips/{trip['id']}", headers=owner_headers)).json()
    assert report["cost_center_code"] == trip_detail["cost_center_code"]
    report_id = report["id"]

    candidates = await client.get(
        f"/api/v1/expenses/{report_id}/match-candidates", headers=owner_headers
    )
    assert candidates.status_code == 200
    rows = candidates.json()
    assert rows, "시드는 완료 출장 기간에 카드거래를 만들어 둔다"
    assert rows[0]["reasons"]

    added = await client.post(
        f"/api/v1/expenses/{report_id}/items",
        json={
            "card_transaction_id": rows[0]["transaction_id"],
            "expense_category_code": rows[0]["suggested_category_code"],
        },
        headers=owner_headers,
    )
    assert added.status_code == 201, added.text
    assert added.json()["total_amount_krw"] == rows[0]["amount_krw"]

    patched = await client.patch(
        f"/api/v1/expenses/{report_id}",
        json={"fund_center_code": "FC1010"},
        headers=owner_headers,
    )
    assert patched.status_code == 200

    submitted = await client.post(f"/api/v1/expenses/{report_id}/submit", headers=owner_headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "SUBMITTED"

    approver_headers = await login_as(approver_email)
    inbox = await client.get("/api/v1/expenses?scope=approvals", headers=approver_headers)
    assert any(item["id"] == report_id for item in inbox.json()["items"])

    approved = await client.post(
        f"/api/v1/expenses/{report_id}/approve", headers=approver_headers
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    settled = await client.get(f"/api/v1/trips/{trip['id']}", headers=owner_headers)
    assert settled.json()["status"] == TripStatus.SETTLED.value

    timeline = await client.get(f"/api/v1/trips/{trip['id']}/timeline", headers=owner_headers)
    assert any(entry["to_status"] == "SETTLED" for entry in timeline.json())

    report_timeline = await client.get(
        f"/api/v1/expenses/{report_id}/timeline", headers=owner_headers
    )
    assert [entry["action"] for entry in report_timeline.json()][-1] == "APPROVED"


async def test_creating_a_report_twice_returns_409_with_a_machine_readable_code(
    client, login_as, seeded
):
    headers, trip, _ = await _owner_with_settleable_trip(client, login_as)
    first = await client.post("/api/v1/expenses", json={"trip_id": trip["id"]}, headers=headers)
    assert first.status_code == 201
    second = await client.post("/api/v1/expenses", json={"trip_id": trip["id"]}, headers=headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "EXPENSE_ALREADY_EXISTS"


async def test_submitting_without_a_fund_center_returns_400_with_the_field(
    client, login_as, seeded
):
    headers, trip, _ = await _owner_with_settleable_trip(client, login_as)
    report_id = (
        await client.post("/api/v1/expenses", json={"trip_id": trip["id"]}, headers=headers)
    ).json()["id"]
    await client.post(
        f"/api/v1/expenses/{report_id}/items",
        json={"expense_category_code": "MEAL", "amount_krw": "12000"},
        headers=headers,
    )
    response = await client.post(f"/api/v1/expenses/{report_id}/submit", headers=headers)
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "CENTER_REQUIRED"
    assert body["field"] == "fund_center_code"


async def test_someone_elses_report_is_a_404(client, login_as, seeded):
    owner_headers, trip, _ = await _owner_with_settleable_trip(client, login_as)
    report_id = (
        await client.post(
            "/api/v1/expenses", json={"trip_id": trip["id"]}, headers=owner_headers
        )
    ).json()["id"]

    stranger_headers = await _stranger_headers(client, login_as, trip)
    response = await client.get(f"/api/v1/expenses/{report_id}", headers=stranger_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXPENSE_NOT_FOUND"


async def test_item_delete_returns_the_updated_report(client, login_as, seeded):
    headers, trip, _ = await _owner_with_settleable_trip(client, login_as)
    report_id = (
        await client.post("/api/v1/expenses", json={"trip_id": trip["id"]}, headers=headers)
    ).json()["id"]
    item_id = (
        await client.post(
            f"/api/v1/expenses/{report_id}/items",
            json={"expense_category_code": "MEAL", "amount_krw": "12000"},
            headers=headers,
        )
    ).json()["items"][0]["id"]

    response = await client.delete(f"/api/v1/expense-items/{item_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total_amount_krw"] == "0.00"


async def test_expense_endpoints_require_authentication(client):
    for method, path in [
        ("get", "/api/v1/expenses"),
        ("get", "/api/v1/expenses/1"),
        ("get", "/api/v1/expenses/1/match-candidates"),
    ]:
        response = await getattr(client, method)(path)
        assert response.status_code == 401, path
    response = await client.post("/api/v1/expenses", json={"trip_id": 1})
    assert response.status_code == 401
