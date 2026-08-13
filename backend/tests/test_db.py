from sqlalchemy import text


async def test_session_fixture_can_query(db_session):
    result = await db_session.execute(text("SELECT 1"))

    assert result.scalar_one() == 1
