"""FC/CC 라우터. 두 리소스가 같은 서비스를 모델만 바꿔 호출한다.

경로를 하나로 합치고 `kind`를 path 파라미터로 받는 방법은 쓰지 않는다 —
`/admin/{kind}`는 스코프 표에서 두 리소스를 구분할 수 없게 만들고, OpenAPI에서도
어떤 값이 유효한지 드러나지 않는다.
"""

from fastapi import APIRouter, status

from app.deps import AdminUser, DbSession
from app.models import CostCenter, FundCenter
from app.schemas.admin import AdminCenterOut, CenterCreate, CenterUpdate
from app.services.admin import centers as service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/fund-centers", response_model=list[AdminCenterOut])
async def list_fund_centers(user: AdminUser, session: DbSession) -> list[AdminCenterOut]:
    return await service.list_centers(session, FundCenter)


@router.post(
    "/fund-centers", response_model=AdminCenterOut, status_code=status.HTTP_201_CREATED
)
async def create_fund_center(
    payload: CenterCreate, user: AdminUser, session: DbSession
) -> AdminCenterOut:
    return await service.create_center(session, FundCenter, payload=payload)


@router.patch("/fund-centers/{center_id}", response_model=AdminCenterOut)
async def update_fund_center(
    center_id: int, payload: CenterUpdate, user: AdminUser, session: DbSession
) -> AdminCenterOut:
    return await service.update_center(
        session, FundCenter, center_id=center_id, payload=payload
    )


@router.delete("/fund-centers/{center_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fund_center(center_id: int, user: AdminUser, session: DbSession) -> None:
    await service.delete_center(session, FundCenter, center_id=center_id)


@router.get("/cost-centers", response_model=list[AdminCenterOut])
async def list_cost_centers(user: AdminUser, session: DbSession) -> list[AdminCenterOut]:
    return await service.list_centers(session, CostCenter)


@router.post(
    "/cost-centers", response_model=AdminCenterOut, status_code=status.HTTP_201_CREATED
)
async def create_cost_center(
    payload: CenterCreate, user: AdminUser, session: DbSession
) -> AdminCenterOut:
    return await service.create_center(session, CostCenter, payload=payload)


@router.patch("/cost-centers/{center_id}", response_model=AdminCenterOut)
async def update_cost_center(
    center_id: int, payload: CenterUpdate, user: AdminUser, session: DbSession
) -> AdminCenterOut:
    return await service.update_center(
        session, CostCenter, center_id=center_id, payload=payload
    )


@router.delete("/cost-centers/{center_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cost_center(center_id: int, user: AdminUser, session: DbSession) -> None:
    await service.delete_center(session, CostCenter, center_id=center_id)
