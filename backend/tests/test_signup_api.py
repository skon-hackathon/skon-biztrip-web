"""가입 API. 미인증 경로이므로 토큰 없이 호출한다."""

import pytest
from sqlalchemy import select

from app.enums import UserStatus
from app.models import User
from tests.factories import make_department, make_user

_PW = "signup1234!"


async def _department_id(db_session) -> int:
    department = await make_department(db_session)
    await db_session.flush()
    return department.id


async def test_public_departments_needs_no_token(client, db_session):
    await _department_id(db_session)
    await db_session.commit()

    response = await client.get("/api/v1/auth/departments")
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    # id·name만 낸다. 다른 필드가 새면 안 된다.
    assert set(body[0]) == {"id", "name"}


async def test_signup_creates_pending_user(client, db_session):
    department_id = await _department_id(db_session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "newcomer@skon.example",
            "password": _PW,
            "name": "새사람",
            "department_id": department_id,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING"
    assert "access_token" not in body  # 승인 전에 토큰을 주면 거짓말이 된다

    user = await db_session.scalar(
        select(User).where(User.email == "newcomer@skon.example")
    )
    assert user is not None
    assert user.status is UserStatus.PENDING
    assert user.is_active is False
    assert user.employee_no is None
    assert user.position_code is None


async def test_signup_rejects_short_password(client, db_session):
    department_id = await _department_id(db_session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "short@skon.example",
            "password": "1234",
            "name": "짧은비번",
            "department_id": department_id,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PASSWORD_TOO_SHORT"


async def test_signup_rejects_unknown_department(client, db_session):
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "nodept@skon.example",
            "password": _PW,
            "name": "부서없음",
            "department_id": 999999,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DEPARTMENT"


async def test_signup_conflicts_with_active_email(client, db_session):
    user = await make_user(db_session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": user.email,
            "password": _PW,
            "name": "중복",
            "department_id": user.department_id,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_EMAIL"


async def test_signup_conflicts_with_pending_email(client, db_session):
    """대기 중인 신청은 덮어쓰지 않는다 — 계정 탈취 경로가 된다."""
    user = await make_user(db_session, status=UserStatus.PENDING, is_active=False)
    original_hash = user.password_hash
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": user.email,
            "password": "attacker-known-pw",
            "name": "가로채기",
            "department_id": user.department_id,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_PENDING"

    await db_session.refresh(user)
    assert user.password_hash == original_hash  # 비밀번호가 덮이지 않았다


async def test_signup_resubmits_after_rejection(client, db_session):
    user = await make_user(db_session, status=UserStatus.REJECTED, is_active=False)
    original_hash = user.password_hash
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": user.email,
            "password": _PW,
            "name": "재신청",
            "department_id": user.department_id,
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "PENDING"

    await db_session.refresh(user)
    assert user.status is UserStatus.PENDING
    assert user.is_active is False
    assert user.name == "재신청"
    assert user.password_hash != original_hash
