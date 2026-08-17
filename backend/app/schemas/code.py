from typing import Any

from pydantic import BaseModel


class CodeOut(BaseModel):
    code: str
    name: str
    sort_order: int
    extra: dict[str, Any]


class CodeGroupOut(BaseModel):
    group_code: str
    name: str
    description: str | None
    codes: list[CodeOut]
