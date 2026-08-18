"""API Key 발급·인증. 평문은 발급 응답에만 존재하고 DB에는 해시만 남는다."""

import hashlib

from app.services.api_keys import KEY_PREFIX, generate_key, hash_key


def test_generate_key_returns_prefixed_plaintext():
    raw, prefix, digest = generate_key()
    assert raw.startswith(KEY_PREFIX)
    assert len(raw) == len(KEY_PREFIX) + 32
    assert raw[len(KEY_PREFIX) :].isalnum()


def test_prefix_is_the_display_head_of_the_raw_key():
    raw, prefix, _ = generate_key()
    assert prefix == raw[:16]
    assert len(prefix) <= 30  # api_key.key_prefix 컬럼 길이


def test_hash_is_sha256_hex_of_the_raw_key():
    raw, _, digest = generate_key()
    assert digest == hashlib.sha256(raw.encode()).hexdigest()
    assert len(digest) == 64  # api_key.key_hash 컬럼 길이


def test_generate_key_is_not_deterministic():
    assert generate_key()[0] != generate_key()[0]


def test_hash_key_matches_generate_key():
    raw, _, digest = generate_key()
    assert hash_key(raw) == digest


from datetime import datetime, timedelta, timezone

import pytest

from app.enums import ApiKeyScope
from app.errors import AuthError
from app.services.api_keys import authenticate_key, key_state
from tests.factories import make_api_key, make_user


def _now() -> datetime:
    return datetime(2026, 8, 18, 3, 0, tzinfo=timezone.utc)


async def test_authenticate_returns_owner_and_scopes(db_session):
    user = await make_user(db_session)
    raw, _ = await make_api_key(
        db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ, ApiKeyScope.CARDS_READ]
    )

    principal, scopes = await authenticate_key(db_session, raw)

    assert principal.id == user.id
    assert scopes == ["trips:read", "cards:read"]


async def test_unknown_key_is_rejected(db_session):
    with pytest.raises(AuthError) as exc:
        await authenticate_key(db_session, "sk_live_" + "0" * 32)
    assert exc.value.code == "INVALID_API_KEY"


async def test_malformed_key_is_rejected_without_a_query(db_session):
    with pytest.raises(AuthError) as exc:
        await authenticate_key(db_session, "not-a-key")
    assert exc.value.code == "INVALID_API_KEY"


async def test_revoked_key_is_rejected_with_its_own_code(db_session):
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, revoked_at=_now())
    with pytest.raises(AuthError) as exc:
        await authenticate_key(db_session, raw)
    assert exc.value.code == "API_KEY_REVOKED"


async def test_expired_key_is_rejected_with_its_own_code(db_session):
    user = await make_user(db_session)
    raw, _ = await make_api_key(
        db_session, user=user, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    with pytest.raises(AuthError) as exc:
        await authenticate_key(db_session, raw)
    assert exc.value.code == "API_KEY_EXPIRED"


async def test_key_of_an_inactive_user_is_rejected(db_session):
    user = await make_user(db_session)
    user.is_active = False
    await db_session.flush()
    raw, _ = await make_api_key(db_session, user=user)
    with pytest.raises(AuthError) as exc:
        await authenticate_key(db_session, raw)
    assert exc.value.code == "INVALID_API_KEY"


async def test_successful_authentication_stamps_last_used_at(db_session):
    user = await make_user(db_session)
    raw, key = await make_api_key(db_session, user=user)
    assert key.last_used_at is None

    await authenticate_key(db_session, raw)
    await db_session.refresh(key)

    assert key.last_used_at is not None


def test_key_state_is_pure():
    active = _now()
    assert key_state(revoked_at=None, expires_at=None, now=active) == "ACTIVE"
    assert key_state(revoked_at=active, expires_at=None, now=active) == "REVOKED"
    assert (
        key_state(revoked_at=None, expires_at=active - timedelta(seconds=1), now=active)
        == "EXPIRED"
    )
    assert (
        key_state(revoked_at=None, expires_at=active + timedelta(days=1), now=active) == "ACTIVE"
    )
    # 폐기가 만료보다 우선 — 사용자가 명시적으로 끈 것이 더 중요한 사실이다
    assert (
        key_state(revoked_at=active, expires_at=active - timedelta(days=1), now=active)
        == "REVOKED"
    )
