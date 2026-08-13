import pytest
from fastapi import FastAPI
import httpx

from app.errors import (
    AppError,
    ConflictError,
    NotFoundError,
    ValidationError,
    register_error_handlers,
)


def test_app_error_carries_code_and_status():
    error = ConflictError("TRIP_NOT_SUBMITTABLE", "이미 상신된 출장입니다")

    assert error.status_code == 409
    assert error.code == "TRIP_NOT_SUBMITTABLE"
    assert error.field is None


def test_not_found_is_404():
    assert NotFoundError("TRIP_NOT_FOUND", "없음").status_code == 404


def test_validation_error_keeps_field():
    error = ValidationError("INVALID_CODE", "잘못된 코드", field="transport_code")

    assert error.status_code == 400
    assert error.field == "transport_code"


async def test_handler_returns_unified_body():
    test_app = FastAPI()
    register_error_handlers(test_app)

    @test_app.get("/boom")
    async def boom():
        raise ConflictError("TRIP_NOT_SUBMITTABLE", "이미 상신된 출장입니다")

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/boom")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "TRIP_NOT_SUBMITTABLE",
            "message": "이미 상신된 출장입니다",
            "field": None,
        }
    }


def test_app_error_is_base_class():
    with pytest.raises(AppError):
        raise NotFoundError("X", "y")
