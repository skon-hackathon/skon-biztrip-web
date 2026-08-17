from sqlalchemy import select

from app.models import CostCenter


async def test_centers_require_authentication(client, seeded):
    assert (await client.get("/api/v1/cost-centers")).status_code == 401


async def test_list_cost_centers(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/cost-centers", headers=headers)

    assert response.status_code == 200
    codes = [center["code"] for center in response.json()]
    assert "CC2030" in codes
    assert codes == sorted(codes)


async def test_list_fund_centers(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/fund-centers", headers=headers)

    assert response.status_code == 200
    assert "FC1010" in [center["code"] for center in response.json()]


async def test_cost_and_fund_centers_do_not_leak_into_each_other(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    cost = {c["code"] for c in (await client.get("/api/v1/cost-centers", headers=headers)).json()}
    fund = {c["code"] for c in (await client.get("/api/v1/fund-centers", headers=headers)).json()}

    assert cost & fund == set()


async def test_inactive_centers_are_hidden(client, seeded, login_as, db_session):
    center = (
        await db_session.execute(select(CostCenter).where(CostCenter.code == "CC2030"))
    ).scalar_one()
    center.is_active = False
    await db_session.flush()
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/cost-centers", headers=headers)

    assert "CC2030" not in [center["code"] for center in response.json()]
