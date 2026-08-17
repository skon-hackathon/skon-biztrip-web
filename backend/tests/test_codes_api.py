from sqlalchemy import select

from app.models import Code, CodeGroup


async def test_codes_require_authentication(client, seeded):
    assert (await client.get("/api/v1/codes")).status_code == 401


async def test_list_all_groups(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/codes", headers=headers)

    assert response.status_code == 200
    groups = {group["group_code"] for group in response.json()}
    assert {"TRIP_PURPOSE", "DESTINATION_TYPE", "TRANSPORT", "ACCOMMODATION", "COUNTRY"} <= groups


async def test_get_one_group_sorted_with_extra(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/codes/COUNTRY", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["group_code"] == "COUNTRY"
    assert [code["sort_order"] for code in body["codes"]] == sorted(
        code["sort_order"] for code in body["codes"]
    )
    korea = next(code for code in body["codes"] if code["code"] == "KR")
    assert korea["extra"]["currency"] == "KRW"


async def test_unknown_group_is_404(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/codes/NOPE", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CODE_GROUP_NOT_FOUND"


async def test_inactive_codes_are_hidden(client, seeded, login_as, db_session):
    group_id = (
        await db_session.execute(select(CodeGroup.id).where(CodeGroup.group_code == "TRANSPORT"))
    ).scalar_one()
    code = (
        await db_session.execute(
            select(Code).where(Code.group_id == group_id, Code.code == "BUS")
        )
    ).scalar_one()
    code.is_active = False
    await db_session.flush()
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/codes/TRANSPORT", headers=headers)

    assert "BUS" not in {item["code"] for item in response.json()["codes"]}


async def test_inactive_group_is_hidden_from_the_list_and_404s(client, seeded, login_as, db_session):
    group = (
        await db_session.execute(select(CodeGroup).where(CodeGroup.group_code == "TRANSPORT"))
    ).scalar_one()
    group.is_active = False
    await db_session.flush()
    headers = await login_as("user1@skon.example")

    listed = await client.get("/api/v1/codes", headers=headers)
    single = await client.get("/api/v1/codes/TRANSPORT", headers=headers)

    assert "TRANSPORT" not in {g["group_code"] for g in listed.json()}
    assert single.status_code == 404
