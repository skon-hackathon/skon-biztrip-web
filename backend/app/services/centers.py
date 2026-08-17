"""Fund Center / Cost Center 마스터 조회와 검증.

공통코드가 아니라 전용 테이블이라 `services/codes.py`와 분리하되, 실패 시 에러 모양은
같게 맞춘다 (400 / field 지정). 호출부가 두 종류의 마스터를 구분해서 다룰 이유가 없다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ValidationError
from app.schemas.center import CenterOut
from app.models import CostCenter, FundCenter

CenterModel = type[FundCenter] | type[CostCenter]


async def load_active_center_codes(session: AsyncSession, model: CenterModel) -> set[str]:
    """`model`을 파라미터로 받는 이유: Phase 2에서는 `assert_cost_center`가 항상
    `CostCenter`만 넘기는 유일한 프로덕션 호출부다. `FundCenter` 인자는 지금은 테스트
    에서만 쓰인다 — Phase 3의 전표 정산 쓰기 경로가 `assert_fund_center`를 추가할 때
    똑같은 조회가 필요해서 미리 모델 파라미터로 열어둔 것이다.

    활성 코드 전체를 집합으로 읽어오는 것도 이 테이블이 작기 때문에 괜찮다 (seed 기준
    cost_center 10개, fund_center 6개). `validate_codes`가 집합을 쓰는 이유(필드 여러
    개를 쿼리 하나로 묶어 상각하고, 순수 판정 함수가 집합을 소비하는 것)와는 다르다 —
    여기는 필드 하나뿐이라 안 맞는다. `CostCenter.code`는 `unique=True, index=True`라
    단일 값 조회라면 인덱스를 타는 존재 여부 확인(`EXISTS`)이 더 자연스럽다. 마스터가
    더 이상 작지 않다면 이 모양을 그대로 베끼지 말 것.
    """
    rows = await session.execute(select(model.code).where(model.is_active.is_(True)))
    return set(rows.scalars().all())


async def assert_cost_center(
    session: AsyncSession, code: str | None, *, field: str = "cost_center_code"
) -> None:
    allowed = await load_active_center_codes(session, CostCenter)
    if code not in allowed:
        raise ValidationError(
            "INVALID_COST_CENTER", f"사용할 수 없는 코스트센터입니다: {code}", field=field
        )


async def load_active_centers(session: AsyncSession, model: CenterModel) -> list[CenterOut]:
    """활성 센터를 코드 순으로 돌려준다.

    load_active_center_codes와 달리 이름·부서까지 필요해서 엔티티를 읽는다 — 화면
    드롭다운은 코드만으로는 못 쓴다. 쿼리를 라우터에 두지 않는 이유는 is_active 필터가
    두 곳에 생기면 나중에 한쪽만 고치기 때문이다.
    """
    rows = (
        (
            await session.execute(
                select(model).where(model.is_active.is_(True)).order_by(model.code)
            )
        )
        .scalars()
        .all()
    )
    return [CenterOut.model_validate(row) for row in rows]
