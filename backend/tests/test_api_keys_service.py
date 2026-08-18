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


from app.errors import ConflictError, NotFoundError, ValidationError
from app.schemas.api_key import ApiKeyCreate
from app.services.api_keys import MAX_ACTIVE_KEYS, create_key, list_keys, revoke_key


async def test_create_returns_plaintext_once_and_stores_only_the_hash(db_session):
    user = await make_user(db_session)
    created = await create_key(
        db_session,
        user=user,
        payload=ApiKeyCreate(name="에이전트 키", scopes=[ApiKeyScope.TRIPS_READ]),
    )

    assert created.key.startswith("sk_live_")
    assert created.key_prefix == created.key[:16]
    # 목록에는 평문이 없다
    listed = await list_keys(db_session, user=user)
    assert not hasattr(listed[0], "key")
    assert listed[0].key_prefix == created.key_prefix


async def test_create_rejects_an_unknown_scope(db_session):
    user = await make_user(db_session)
    with pytest.raises(ValidationError) as exc:
        await create_key(
            db_session, user=user, payload=ApiKeyCreate(name="x", scopes=["trips:delete"])
        )
    assert exc.value.code == "INVALID_SCOPE"
    assert exc.value.field == "scopes"


async def test_create_requires_at_least_one_scope(db_session):
    """스코프 0개 키는 아무 것도 못 하므로 만들 이유가 없다. 만들게 두면 사용자가 헤맨다."""
    user = await make_user(db_session)
    with pytest.raises(ValidationError) as exc:
        await create_key(db_session, user=user, payload=ApiKeyCreate(name="x", scopes=[]))
    assert exc.value.code == "SCOPES_REQUIRED"


async def test_create_deduplicates_scopes(db_session):
    user = await make_user(db_session)
    created = await create_key(
        db_session,
        user=user,
        payload=ApiKeyCreate(
            name="x", scopes=[ApiKeyScope.TRIPS_READ, ApiKeyScope.TRIPS_READ]
        ),
    )
    assert created.scopes == ["trips:read"]


async def test_create_sets_expiry_from_days(db_session):
    user = await make_user(db_session)
    created = await create_key(
        db_session,
        user=user,
        payload=ApiKeyCreate(name="x", scopes=[ApiKeyScope.TRIPS_READ], expires_in_days=30),
    )
    assert created.expires_at is not None
    delta = created.expires_at - datetime.now(timezone.utc)
    assert timedelta(days=29) < delta <= timedelta(days=30)


async def test_create_without_expiry_never_expires(db_session):
    user = await make_user(db_session)
    created = await create_key(
        db_session, user=user, payload=ApiKeyCreate(name="x", scopes=[ApiKeyScope.TRIPS_READ])
    )
    assert created.expires_at is None


async def test_active_key_count_is_capped(db_session):
    user = await make_user(db_session)
    for index in range(MAX_ACTIVE_KEYS):
        await make_api_key(db_session, user=user, name=f"키{index}")

    with pytest.raises(ConflictError) as exc:
        await create_key(
            db_session, user=user, payload=ApiKeyCreate(name="넘침", scopes=[ApiKeyScope.TRIPS_READ])
        )
    assert exc.value.code == "TOO_MANY_KEYS"


async def test_revoked_keys_do_not_count_towards_the_cap(db_session):
    user = await make_user(db_session)
    for index in range(MAX_ACTIVE_KEYS):
        await make_api_key(
            db_session, user=user, name=f"키{index}", revoked_at=datetime.now(timezone.utc)
        )

    created = await create_key(
        db_session, user=user, payload=ApiKeyCreate(name="새 키", scopes=[ApiKeyScope.TRIPS_READ])
    )
    assert created.key.startswith("sk_live_")


async def test_list_shows_only_my_keys_newest_first(db_session):
    mine = await make_user(db_session, name="나")
    other = await make_user(db_session, name="남")
    await make_api_key(db_session, user=other, name="남의 키")
    await make_api_key(db_session, user=mine, name="내 키 1")
    await make_api_key(db_session, user=mine, name="내 키 2")

    listed = await list_keys(db_session, user=mine)

    assert [item.name for item in listed] == ["내 키 2", "내 키 1"]


async def test_list_reports_state(db_session):
    user = await make_user(db_session)
    await make_api_key(db_session, user=user, name="살아있음")
    await make_api_key(
        db_session, user=user, name="만료됨", expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    await make_api_key(db_session, user=user, name="폐기됨", revoked_at=datetime.now(timezone.utc))

    states = {item.name: item.state for item in await list_keys(db_session, user=user)}

    assert states == {"살아있음": "ACTIVE", "만료됨": "EXPIRED", "폐기됨": "REVOKED"}


async def test_revoke_marks_the_key_and_kills_authentication(db_session):
    user = await make_user(db_session)
    raw, key = await make_api_key(db_session, user=user)

    result = await revoke_key(db_session, user=user, key_id=key.id)

    assert result.state == "REVOKED"
    with pytest.raises(AuthError) as exc:
        await authenticate_key(db_session, raw)
    assert exc.value.code == "API_KEY_REVOKED"


async def test_revoking_someone_elses_key_is_404(db_session):
    mine = await make_user(db_session, name="나")
    other = await make_user(db_session, name="남")
    _, key = await make_api_key(db_session, user=other)

    with pytest.raises(NotFoundError) as exc:
        await revoke_key(db_session, user=mine, key_id=key.id)
    assert exc.value.code == "API_KEY_NOT_FOUND"


async def test_revoking_twice_is_409(db_session):
    user = await make_user(db_session)
    _, key = await make_api_key(db_session, user=user, revoked_at=datetime.now(timezone.utc))

    with pytest.raises(ConflictError) as exc:
        await revoke_key(db_session, user=user, key_id=key.id)
    assert exc.value.code == "API_KEY_ALREADY_REVOKED"
