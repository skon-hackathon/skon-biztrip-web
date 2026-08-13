from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ValidationError
from app.models import Code, CodeGroup


def assert_valid_code(
    group_code: str, value: str | None, allowed: set[str], *, field: str
) -> None:
    """순수 검증 — DB 접근 없음. 허용 집합은 호출자가 주입한다."""
    if value not in allowed:
        raise ValidationError(
            "INVALID_CODE",
            f"{group_code} 그룹에 없는 코드값입니다: {value}",
            field=field,
        )


async def load_active_codes(session: AsyncSession, group_code: str) -> set[str]:
    group_id = (
        await session.execute(select(CodeGroup.id).where(CodeGroup.group_code == group_code))
    ).scalar_one_or_none()
    if group_id is None:
        raise ValidationError("UNKNOWN_CODE_GROUP", f"존재하지 않는 코드그룹입니다: {group_code}")

    rows = await session.execute(
        select(Code.code).where(Code.group_id == group_id, Code.is_active.is_(True))
    )
    return set(rows.scalars().all())
