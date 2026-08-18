"""API Key 발급·인증·폐기.

평문 키는 발급 응답에서 단 한 번만 나가고 DB에는 SHA-256 해시만 남는다(spec 5.7).
비밀번호와 달리 bcrypt를 쓰지 않는 이유: 키는 128비트 난수라 사전공격 대상이 아니고,
매 API 호출마다 bcrypt를 태우면 요청당 수십 ms가 그냥 사라진다.
"""

import hashlib
import secrets

#: 평문 키 접두어. spec 5.7의 표기를 그대로 쓴다.
KEY_PREFIX = "sk_live_"
#: 목록에 보여줄 앞부분 길이. 접두어(8) + 난수 8자.
PREFIX_DISPLAY_LEN = 16


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_key() -> tuple[str, str, str]:
    """(평문, 표시용 접두어, 해시)를 만든다. 평문은 호출자가 즉시 응답에 실어 보내고 버린다."""
    raw = f"{KEY_PREFIX}{secrets.token_hex(16)}"
    return raw, raw[:PREFIX_DISPLAY_LEN], hash_key(raw)
