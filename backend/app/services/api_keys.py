"""API Key 발급·인증·폐기.

평문 키는 발급 응답에서 단 한 번만 나가고 DB에는 SHA-256 해시만 남는다(spec 5.7).
비밀번호와 달리 bcrypt를 쓰지 않는 이유: 키는 128비트 난수라 사전공격 대상이 아니고,
매 API 호출마다 bcrypt를 태우면 요청당 수십 ms가 그냥 사라진다.
"""

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AuthError
from app.models import ApiKey, User

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


def key_state(
    *, revoked_at: datetime | None, expires_at: datetime | None, now: datetime
) -> str:
    """ACTIVE | REVOKED | EXPIRED. 목록 표시와 인증 판정이 같은 규칙을 쓰게 하려고 순수 함수로 둔다."""
    if revoked_at is not None:
        return "REVOKED"
    if expires_at is not None and expires_at <= now:
        return "EXPIRED"
    return "ACTIVE"


async def authenticate_key(session: AsyncSession, raw: str) -> tuple[User, list[str]]:
    """평문 키로 소유자와 스코프를 얻는다. 실패는 전부 401이다.

    폐기·만료를 각각 다른 코드로 돌려주는 이유: Agent가 "키를 갱신하면 되는 상황"과
    "관리자가 끈 상황"을 구분해야 재시도 여부를 판단할 수 있다. 존재하지 않는 키는
    이 둘과 섞어 `INVALID_API_KEY` 하나로 뭉갠다 — 남의 키의 상태를 알려줄 이유가 없다.
    """
    if not raw.startswith(KEY_PREFIX):
        raise AuthError("INVALID_API_KEY", "유효하지 않은 API Key입니다")

    key = (
        await session.execute(select(ApiKey).where(ApiKey.key_hash == hash_key(raw)))
    ).scalar_one_or_none()
    if key is None:
        raise AuthError("INVALID_API_KEY", "유효하지 않은 API Key입니다")

    now = datetime.now(timezone.utc)
    state = key_state(revoked_at=key.revoked_at, expires_at=key.expires_at, now=now)
    if state == "REVOKED":
        raise AuthError("API_KEY_REVOKED", "폐기된 API Key입니다")
    if state == "EXPIRED":
        raise AuthError("API_KEY_EXPIRED", "만료된 API Key입니다")

    user = await session.get(User, key.user_id)
    # 퇴사 처리된 사용자의 키가 계속 살아 있으면 안 된다. 키가 아니라 사용자 쪽 문제이므로
    # 상태를 구분해 알려주지 않는다.
    if user is None or not user.is_active:
        raise AuthError("INVALID_API_KEY", "유효하지 않은 API Key입니다")

    key.last_used_at = now
    await session.flush()
    return user, list(key.scopes)
