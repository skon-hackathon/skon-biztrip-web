from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """목록 응답의 공통 봉투. Agent가 total만 보고 페이징 여부를 판단할 수 있게 한다."""

    items: list[T]
    total: int
    page: int
    size: int
