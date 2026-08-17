from fastapi import APIRouter

from app.deps import CurrentUser, DbSession
from app.schemas.code import CodeGroupOut
from app.services import codes as code_service

router = APIRouter(prefix="/api/v1/codes", tags=["codes"])


@router.get("", response_model=list[CodeGroupOut])
async def list_code_groups(user: CurrentUser, session: DbSession) -> list[CodeGroupOut]:
    return await code_service.load_code_groups(session)


@router.get("/{group_code}", response_model=CodeGroupOut)
async def get_code_group(group_code: str, user: CurrentUser, session: DbSession) -> CodeGroupOut:
    return await code_service.load_code_group(session, group_code)
