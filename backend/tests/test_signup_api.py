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


async def test_signup_rejects_case_variant_of_pending_email(client, db_session):
    """대소문자만 다른 이메일이 ALREADY_PENDING 가드를 우회하면 안 된다.

    Postgres의 `=`도 unique 인덱스도 대소문자를 구분한다. 정규화하지 않으면 남이
    신청해 둔 대기 계정 옆에 사실상 같은 주소의 행이 하나 더 생기고, 관리자가
    그중 공격자의 행을 승인할 수 있다.
    """
    user = await make_user(db_session, status=UserStatus.PENDING, is_active=False)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": user.email.upper(),
            "password": "attacker-known-pw",
            "name": "가로채기",
            "department_id": user.department_id,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_PENDING"


async def test_signup_rejects_case_variant_of_active_email(client, db_session):
    user = await make_user(db_session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": user.email.upper(),
            "password": "signup1234!",
            "name": "중복",
            "department_id": user.department_id,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_EMAIL"


async def test_signup_stores_email_lowercased(client, db_session):
    department_id = await _department_id(db_session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "MixedCase@skon.example",
            "password": "signup1234!",
            "name": "혼합대소",
            "department_id": department_id,
        },
    )
    assert response.status_code == 201
    assert response.json()["email"] == "mixedcase@skon.example"

    stored = await db_session.scalar(
        select(User).where(User.email == "mixedcase@skon.example")
    )
    assert stored is not None


async def test_concurrent_signup_is_409_not_500(client, db_session, monkeypatch):
    """유니크 위반이 500이 되면 Agent가 절대 성공할 수 없는 요청을 재시도한다.

    select와 commit 사이의 TOCTOU를 강제로 재현한다 — 존재 조회가 못 찾은 척하게
    만들고, DB의 유니크 제약이 대신 잡게 둔다.
    """
    user = await make_user(db_session)
    await db_session.commit()

    real_scalar = db_session.scalar

    async def _miss(statement, *args, **kwargs):
        # User 존재 조회만 None으로 만든다. 다른 조회는 그대로 통과시킨다.
        result = await real_scalar(statement, *args, **kwargs)
        if isinstance(result, User):
            return None
        return result

    monkeypatch.setattr(db_session, "scalar", _miss)

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": user.email,
            "password": _PW,
            "name": "동시가입",
            "department_id": user.department_id,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_EMAIL"
