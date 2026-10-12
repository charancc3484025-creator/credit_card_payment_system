from datetime import datetime, timezone
from math import ceil
from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict, PlainSerializer


def _to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


UTCDateTime = Annotated[datetime, PlainSerializer(_to_utc_iso, return_type=str)]

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    success: bool = True
    message: str


class Page(BaseModel, Generic[T]):
    count: int
    page: int
    page_size: int
    total_pages: int
    results: list[T]


class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def paginate(query, params: PageParams, convert) -> dict:
    total = query.order_by(None).count()
    items = query.offset(params.offset).limit(params.page_size).all()
    return {
        "count": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": ceil(total / params.page_size) if total else 0,
        "results": [convert(item) for item in items],
    }
