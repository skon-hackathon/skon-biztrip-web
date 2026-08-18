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
