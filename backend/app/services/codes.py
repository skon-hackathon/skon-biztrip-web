from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ValidationError
from app.models import Code, CodeGroup

#: (group_code, 응답 field 이름, 검증할 값)
CodeSpec = tuple[str, str, str | None]


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


async def validate_codes(session: AsyncSession, specs: Sequence[CodeSpec]) -> None:
    """여러 코드값을 한 번에 검증한다.

    호출부가 `load_active_codes` + `assert_valid_code`를 필드 수만큼 반복하면 그룹명과
    field 문자열을 잘못 짝짓기 쉽다. 그 실수를 구조적으로 막는 것이 이 함수의 목적이다.

    `asyncio.gather`로 병렬화하지 않는다 — AsyncSession은 동시 사용이 금지돼 있어
    같은 세션에 execute를 병렬로 걸면 InvalidRequestError가 난다. 대신 그룹 수와
    무관하게 쿼리 2개로 끝낸다.

    실패는 specs 순서대로 보고한다. 어떤 필드가 먼저 걸리는지가 결정적이어야
    호출부와 테스트가 흔들리지 않는다.
    """
    wanted = {group_code for group_code, _, _ in specs}
    group_rows = await session.execute(
        select(CodeGroup.id, CodeGroup.group_code).where(
            CodeGroup.group_code.in_(wanted), CodeGroup.is_active.is_(True)
        )
    )
    group_id_by_code = {group_code: group_id for group_id, group_code in group_rows}

    for group_code, _, _ in specs:
        if group_code not in group_id_by_code:
            raise ValidationError(
                "UNKNOWN_CODE_GROUP", f"존재하지 않는 코드그룹입니다: {group_code}"
            )

    code_rows = await session.execute(
        select(Code.group_id, Code.code).where(
            Code.group_id.in_(group_id_by_code.values()), Code.is_active.is_(True)
        )
    )
    allowed: dict[int, set[str]] = defaultdict(set)
    for group_id, code in code_rows:
        allowed[group_id].add(code)

    for group_code, field, value in specs:
        assert_valid_code(
            group_code, value, allowed[group_id_by_code[group_code]], field=field
        )
