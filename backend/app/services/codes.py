from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError, ValidationError
from app.models import Code, CodeGroup
from app.schemas.code import CodeGroupOut, CodeOut

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

    보고 순서는 단일 정렬이 아니라 두 단계다: 그룹 존재 여부(UNKNOWN_CODE_GROUP)를
    specs 순서대로 전부 확인한 뒤에야 코드값(INVALID_CODE)을 specs 순서대로 확인한다.
    설정 오류(존재하지 않는 그룹)가 사용자 오타보다 항상 먼저 보고된다는 뜻이다.
    각 단계 안에서는 specs 순서가 그대로 유지된다.
    """
    if not specs:
        return

    wanted = {group_code for group_code, _, _ in specs}
    group_rows = await session.execute(
        select(CodeGroup.id, CodeGroup.group_code).where(
            CodeGroup.group_code.in_(wanted), CodeGroup.is_active.is_(True)
        )
    )
    group_id_by_code = {group_code: group_id for group_id, group_code in group_rows}

    for group_code, field, _ in specs:
        if group_code not in group_id_by_code:
            raise ValidationError(
                "UNKNOWN_CODE_GROUP",
                f"존재하지 않는 코드그룹입니다: {group_code}",
                field=field,
            )

    code_rows = await session.execute(
        select(Code.group_id, Code.code).where(
            Code.group_id.in_(group_id_by_code.values()), Code.is_active.is_(True)
        )
    )
    allowed: dict[int, set[str]] = {}
    for group_id, code in code_rows:
        allowed.setdefault(group_id, set()).add(code)

    for group_code, field, value in specs:
        assert_valid_code(
            group_code,
            value,
            allowed.get(group_id_by_code[group_code], set()),
            field=field,
        )


def _to_group_out(group: CodeGroup) -> CodeGroupOut:
    """CodeGroup.codes는 lazy="selectin"이라 그룹 조회 한 번에 함께 실려온다.
    비활성 코드는 여기서 걸러낸다 — 관리자만 보는 값을 폼 드롭다운에 내보내지 않는다."""
    return CodeGroupOut(
        group_code=group.group_code,
        name=group.name,
        description=group.description,
        codes=[
            CodeOut(code=code.code, name=code.name, sort_order=code.sort_order, extra=code.extra)
            for code in sorted(
                (code for code in group.codes if code.is_active), key=lambda c: c.sort_order
            )
        ],
    )


async def load_code_groups(session: AsyncSession) -> list[CodeGroupOut]:
    groups = (
        (
            await session.execute(
                select(CodeGroup)
                .where(CodeGroup.is_active.is_(True))
                .order_by(CodeGroup.group_code)
            )
        )
        .scalars()
        .all()
    )
    return [_to_group_out(group) for group in groups]


async def load_code_group(session: AsyncSession, group_code: str) -> CodeGroupOut:
    group = (
        await session.execute(
            select(CodeGroup).where(
                CodeGroup.group_code == group_code, CodeGroup.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if group is None:
        raise NotFoundError("CODE_GROUP_NOT_FOUND", f"존재하지 않는 코드그룹입니다: {group_code}")
    return _to_group_out(group)
