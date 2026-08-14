from datetime import datetime, timedelta, timezone

import pytest

from app.errors import AuthError
from app.security import create_access_token, decode_access_token, hash_password, verify_password


def test_hash_and_verify_password():
    hashed = hash_password("skon1234!")

    assert hashed != "skon1234!"
    assert verify_password("skon1234!", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_password_rejects_malformed_hash():
    assert verify_password("skon1234!", "not-a-bcrypt-hash") is False


def test_token_roundtrip_carries_user_id():
    token = create_access_token(user_id=42)

    assert decode_access_token(token) == 42


def test_decode_rejects_garbage():
    with pytest.raises(AuthError) as exc_info:
        decode_access_token("garbage.token.value")

    assert exc_info.value.code == "INVALID_TOKEN"


def test_decode_rejects_expired_token():
    expired = create_access_token(
        user_id=7, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )

    with pytest.raises(AuthError) as exc_info:
        decode_access_token(expired)

    assert exc_info.value.code == "TOKEN_EXPIRED"
