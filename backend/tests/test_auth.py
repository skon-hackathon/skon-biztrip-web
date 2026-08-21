from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import User
from app.security import create_access_token
from app.seed import seed_all


async def test_login_returns_token_and_user(client, db_session):
    await seed_all(db_session)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "user1@skon.example", "password": "skon1234!"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["user"]["email"] == "user1@skon.example"
    assert payload["user"]["role"] == "EMPLOYEE"
    assert "password_hash" not in payload["user"]


async def test_login_with_wrong_password_returns_401(client, db_session):
    await seed_all(db_session)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "user1@skon.example", "password": "nope"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_with_unknown_email_returns_401(client, db_session):
    await seed_all(db_session)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@skon.example", "password": "skon1234!"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_me_requires_authentication(client, db_session):
    await seed_all(db_session)

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_CREDENTIALS"


async def test_me_returns_current_user(client, db_session):
    await seed_all(db_session)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "manager1@skon.example", "password": "skon1234!"},
    )
    token = login.json()["access_token"]

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "manager1@skon.example"
    assert body["role"] == "MANAGER"
    assert body["department_name"] == "배터리연구소"


async def test_me_rejects_malformed_token(client, db_session):
    await seed_all(db_session)

    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nonsense"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


async def test_inactive_user_is_rejected_at_login_and_me(client, db_session):
    await seed_all(db_session)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "user1@skon.example", "password": "skon1234!"},
    )
    token = login.json()["access_token"]

    user = (
        await db_session.execute(select(User).where(User.email == "user1@skon.example"))
    ).scalar_one()
    user.is_active = False
    await db_session.flush()

    login_after_deactivation = await client.post(
        "/api/v1/auth/login",
        json={"email": "user1@skon.example", "password": "skon1234!"},
    )
    assert login_after_deactivation.status_code == 401
    assert login_after_deactivation.json()["error"]["code"] == "INVALID_CREDENTIALS"

    me_response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 401
    assert me_response.json()["error"]["code"] == "INVALID_TOKEN"


async def test_me_rejects_expired_token(client, db_session):
    await seed_all(db_session)
    user = (
        await db_session.execute(select(User).where(User.email == "user1@skon.example"))
    ).scalar_one()
    expired_token = create_access_token(
        user_id=user.id, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


async def test_pending_user_with_correct_password_gets_pending_code(client, db_session):
    from app.enums import UserStatus
    from app.security import hash_password
    from tests.factories import make_user

    user = await make_user(db_session, status=UserStatus.PENDING, is_active=False)
    user.password_hash = hash_password("pending1234!")
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "pending1234!"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "PENDING_APPROVAL"


async def test_pending_user_with_wrong_password_leaks_nothing(client, db_session):
    """상태는 비밀번호를 맞힌 사람에게만 알린다. 아니면 계정 존재가 샌다."""
    from app.enums import UserStatus
    from app.security import hash_password
    from tests.factories import make_user

    user = await make_user(db_session, status=UserStatus.PENDING, is_active=False)
    user.password_hash = hash_password("pending1234!")
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_rejected_user_gets_rejected_code(client, db_session):
    from app.enums import UserStatus
    from app.security import hash_password
    from tests.factories import make_user

    user = await make_user(db_session, status=UserStatus.REJECTED, is_active=False)
    user.password_hash = hash_password("rejected1234!")
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "rejected1234!"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SIGNUP_REJECTED"


async def test_suspended_active_user_stays_generic(client, db_session):
    """승인됐지만 관리자가 정지시킨 계정은 기존 메시지를 유지한다."""
    from app.enums import UserStatus
    from app.security import hash_password
    from tests.factories import make_user

    user = await make_user(db_session, status=UserStatus.ACTIVE, is_active=False)
    user.password_hash = hash_password("suspended1234!")
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "suspended1234!"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
