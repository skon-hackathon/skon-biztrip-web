"""Fund Center / Cost Center 마스터 조회와 검증.

공통코드가 아니라 전용 테이블이라 `services/codes.py`와 분리하되, 실패 시 에러 모양은
같게 맞춘다 (400 / field 지정). 호출부가 두 종류의 마스터를 구분해서 다룰 이유가 없다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ValidationError
from app.models import CostCenter, FundCenter

CenterModel = type[FundCenter] | type[CostCenter]


async def load_active_center_codes(session: AsyncSession, model: CenterModel) -> set[str]:
    rows = await session.execute(select(model.code).where(model.is_active.is_(True)))
    return set(rows.scalars().all())


async def assert_cost_center(
    session: AsyncSession, code: str | None, *, field: str = "cost_center_code"
) -> None:
    allowed = await load_active_center_codes(session, CostCenter)
    if code not in allowed:
        raise ValidationError(
            "INVALID_COST_CENTER", f"존재하지 않는 코스트센터입니다: {code}", field=field
        )
