from fastapi import APIRouter

from app.deps import CurrentUser, DbSession
from app.models import CostCenter, FundCenter
from app.schemas.center import CenterOut
from app.services.centers import load_active_centers

router = APIRouter(prefix="/api/v1", tags=["centers"])


@router.get("/fund-centers", response_model=list[CenterOut])
async def list_fund_centers(user: CurrentUser, session: DbSession) -> list[CenterOut]:
    return await load_active_centers(session, FundCenter)


@router.get("/cost-centers", response_model=list[CenterOut])
async def list_cost_centers(user: CurrentUser, session: DbSession) -> list[CenterOut]:
    return await load_active_centers(session, CostCenter)
