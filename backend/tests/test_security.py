from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import get_settings
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


def test_decode_rejects_token_signed_with_wrong_secret():
    payload = {"sub": "5", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    token = jwt.encode(payload, "a-different-secret-value-that-is-not-the-real-one", algorithm="HS256")

    with pytest.raises(AuthError) as exc_info:
        decode_access_token(token)

    assert exc_info.value.code == "INVALID_TOKEN"


def test_decode_rejects_token_without_sub_claim():
    settings = get_settings()
    payload = {"exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    with pytest.raises(AuthError) as exc_info:
        decode_access_token(token)

    assert exc_info.value.code == "INVALID_TOKEN"


def test_decode_rejects_token_with_non_numeric_sub():
    settings = get_settings()
    payload = {"sub": "3.5", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    with pytest.raises(AuthError) as exc_info:
        decode_access_token(token)

    assert exc_info.value.code == "INVALID_TOKEN"
