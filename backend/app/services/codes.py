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
    """엔티티 대신 id 컬럼만 선택한다 — CodeGroup을 select하면 ORM 객체가 만들어지며
    lazy="selectin"인 CodeGroup.codes가 즉시 로드되어 불필요한 세 번째 쿼리가 발생한다.
    쿼리 두 개 구조는 하나의 join으로 합칠 수 없다: join은 "코드그룹이 없거나 비활성"
    (UNKNOWN_CODE_GROUP을 던져야 함)과 "그룹은 존재하지만 활성 코드가 0개"(빈 set()을
    반환해야 함)를 구분하지 못한다."""
    group_id = (
        await session.execute(
            select(CodeGroup.id).where(
                CodeGroup.group_code == group_code,
                CodeGroup.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if group_id is None:
        raise ValidationError("UNKNOWN_CODE_GROUP", f"존재하지 않는 코드그룹입니다: {group_code}")

    rows = await session.execute(
        select(Code.code).where(Code.group_id == group_id, Code.is_active.is_(True))
    )
    return set(rows.scalars().all())
