"""공통코드 그룹·코드 CRUD.

삭제가 2단계인 이유는 참조 방식 때문이다. 업무 테이블은 `trip.transport_code = 'AIR'`처럼
**코드값 문자열**을 저장하므로 FK가 없고, PostgreSQL이 삭제를 막아주지 않는다. 그래서
`delete_entity`(IntegrityError→409)만으로는 아무것도 지켜지지 않는다. 대신 서비스가
"비활성화된 코드만 삭제 가능", "코드가 없는 그룹만 삭제 가능"을 강제한다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, NotFoundError
from app.models import Code, CodeGroup
from app.schemas.admin import (
    AdminCodeGroupOut,
    AdminCodeOut,
    CodeCreate,
    CodeGroupCreate,
    CodeGroupUpdate,
    CodeUpdate,
)
from app.services.admin.common import assert_unique, delete_entity


def _to_out(group: CodeGroup) -> AdminCodeGroupOut:
    """비활성 코드도 포함한다 — 관리 화면이 못 보면 되살릴 수 없다.
    `CodeGroup.codes`는 lazy="selectin"이라 그룹 조회 한 번에 함께 실려온다."""
    return AdminCodeGroupOut(
        id=group.id,
        group_code=group.group_code,
        name=group.name,
        description=group.description,
        is_active=group.is_active,
        codes=[
            AdminCodeOut.model_validate(code)
            for code in sorted(group.codes, key=lambda c: (c.sort_order, c.code))
        ],
    )


async def list_code_groups(session: AsyncSession) -> list[AdminCodeGroupOut]:
    groups = (
        (await session.execute(select(CodeGroup).order_by(CodeGroup.group_code)))
        .scalars()
        .all()
    )
    return [_to_out(group) for group in groups]


async def _load_group(session: AsyncSession, group_id: int) -> CodeGroup:
    group = await session.get(CodeGroup, group_id)
    if group is None:
        raise NotFoundError("CODE_GROUP_NOT_FOUND", f"존재하지 않는 코드그룹입니다: {group_id}")
    return group


async def _load_code(session: AsyncSession, code_id: int) -> Code:
    code = await session.get(Code, code_id)
    if code is None:
        raise NotFoundError("CODE_NOT_FOUND", f"존재하지 않는 코드입니다: {code_id}")
    return code


async def create_code_group(
    session: AsyncSession, *, payload: CodeGroupCreate
) -> AdminCodeGroupOut:
    await assert_unique(
        session,
        CodeGroup.group_code,
        payload.group_code,
        code="DUPLICATE_CODE_GROUP",
        message=f"이미 있는 코드그룹입니다: {payload.group_code}",
        field="group_code",
    )
    group = CodeGroup(
        group_code=payload.group_code,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
    )
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return _to_out(group)


async def update_code_group(
    session: AsyncSession, *, group_id: int, payload: CodeGroupUpdate
) -> AdminCodeGroupOut:
    group = await _load_group(session, group_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(group, field, value)
    await session.commit()
    await session.refresh(group)
    return _to_out(group)


async def delete_code_group(session: AsyncSession, *, group_id: int) -> None:
    group = await _load_group(session, group_id)
    if group.codes:
        raise ConflictError(
            "HAS_DEPENDENTS",
            f"코드 {len(group.codes)}개가 남아 있는 그룹은 삭제할 수 없습니다. "
            "코드를 먼저 지우거나 그룹을 비활성화하세요",
        )
    await delete_entity(session, group, message="이 코드그룹을 참조하는 데이터가 있습니다")


async def create_code(
    session: AsyncSession, *, group_id: int, payload: CodeCreate
) -> AdminCodeOut:
    group = await _load_group(session, group_id)
    # 유니크가 (group_id, code) 복합이라 assert_unique(단일 컬럼)를 쓸 수 없다.
    existing = await session.scalar(
        select(Code.id).where(Code.group_id == group.id, Code.code == payload.code).limit(1)
    )
    if existing is not None:
        raise ConflictError(
            "DUPLICATE_CODE",
            f"{group.group_code} 그룹에 이미 있는 코드입니다: {payload.code}",
            field="code",
        )
    code = Code(
        group_id=group.id,
        code=payload.code,
        name=payload.name,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
        extra=payload.extra,
    )
    session.add(code)
    await session.commit()
    await session.refresh(code)
    return AdminCodeOut.model_validate(code)


async def update_code(
    session: AsyncSession, *, code_id: int, payload: CodeUpdate
) -> AdminCodeOut:
    code = await _load_code(session, code_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(code, field, value)
    await session.commit()
    await session.refresh(code)
    return AdminCodeOut.model_validate(code)


async def delete_code(session: AsyncSession, *, code_id: int) -> None:
    code = await _load_code(session, code_id)
    if code.is_active:
        raise ConflictError(
            "CODE_STILL_ACTIVE",
            "활성 코드는 삭제할 수 없습니다. 먼저 비활성화하세요 "
            "(업무 데이터가 코드값을 문자열로 참조하므로 DB가 막아주지 못합니다)",
        )
    await delete_entity(session, code, message="이 코드를 참조하는 데이터가 있습니다")
