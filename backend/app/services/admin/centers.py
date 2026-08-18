"""Fund Center / Cost Center CRUD.

두 테이블은 컬럼이 같고 규칙도 같아서 모델을 파라미터로 받는다 (`services/centers.py`와 같은
방식). 코드를 두 벌로 두면 한쪽만 고치는 날이 온다.

삭제 전 참조 검사를 서비스가 직접 하는 이유: 업무 테이블은 센터를 **코드 문자열**로 참조하므로
FK가 없고, `delete_entity`의 IntegrityError 변환이 아무것도 잡지 못한다. 참조처가 3곳뿐이라
열거해서 막을 수 있다 — 이 목록은 새 참조처가 생기면 함께 늘려야 한다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import (
    CostCenter,
    Department,
    ExpenseItem,
    ExpenseReport,
    FundCenter,
    Trip,
)
from app.schemas.admin import AdminCenterOut, CenterCreate, CenterUpdate
from app.services.admin.common import assert_unique, delete_entity

CenterModel = type[FundCenter] | type[CostCenter]

#: 모델 -> ((참조 컬럼, 사람이 읽을 이름), ...). FK가 없으므로 이 표가 유일한 방어선이다.
_REFERENCES: dict[CenterModel, tuple[tuple[object, str], ...]] = {
    CostCenter: (
        (Trip.cost_center_code, "출장"),
        (ExpenseReport.cost_center_code, "정산서"),
        (ExpenseItem.cost_center_code, "정산항목"),
    ),
    FundCenter: (
        (ExpenseReport.fund_center_code, "정산서"),
        (ExpenseItem.fund_center_code, "정산항목"),
    ),
}


async def list_centers(session: AsyncSession, model: CenterModel) -> list[AdminCenterOut]:
    """비활성 포함. 활성만 필요한 화면은 기존 `/fund-centers`·`/cost-centers`를 쓴다."""
    rows = (await session.execute(select(model).order_by(model.code))).scalars().all()
    return [AdminCenterOut.model_validate(row) for row in rows]


async def _load(session: AsyncSession, model: CenterModel, center_id: int):
    center = await session.get(model, center_id)
    if center is None:
        raise NotFoundError("CENTER_NOT_FOUND", f"존재하지 않는 센터입니다: {center_id}")
    return center


async def _assert_department(session: AsyncSession, department_id: int | None) -> None:
    if department_id is None:
        return
    if await session.get(Department, department_id) is None:
        raise ValidationError(
            "INVALID_DEPARTMENT",
            f"존재하지 않는 부서입니다: {department_id}",
            field="department_id",
        )


async def create_center(
    session: AsyncSession, model: CenterModel, *, payload: CenterCreate
) -> AdminCenterOut:
    await assert_unique(
        session,
        model.code,
        payload.code,
        code="DUPLICATE_CENTER_CODE",
        message=f"이미 있는 센터 코드입니다: {payload.code}",
        field="code",
    )
    await _assert_department(session, payload.department_id)
    center = model(
        code=payload.code,
        name=payload.name,
        department_id=payload.department_id,
        is_active=payload.is_active,
    )
    session.add(center)
    await session.commit()
    await session.refresh(center)
    return AdminCenterOut.model_validate(center)


async def update_center(
    session: AsyncSession, model: CenterModel, *, center_id: int, payload: CenterUpdate
) -> AdminCenterOut:
    center = await _load(session, model, center_id)
    changes = payload.model_dump(exclude_unset=True)
    if "department_id" in changes:
        await _assert_department(session, changes["department_id"])
    for field, value in changes.items():
        setattr(center, field, value)
    await session.commit()
    await session.refresh(center)
    return AdminCenterOut.model_validate(center)


async def delete_center(session: AsyncSession, model: CenterModel, *, center_id: int) -> None:
    center = await _load(session, model, center_id)
    for column, label in _REFERENCES[model]:
        found = await session.scalar(select(column).where(column == center.code).limit(1))
        if found is not None:
            raise ConflictError(
                "HAS_DEPENDENTS", f"{label}이(가) 이 센터를 참조하고 있어 삭제할 수 없습니다"
            )
    await delete_entity(session, center, message="이 센터를 참조하는 데이터가 있습니다")
