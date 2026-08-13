import pytest
from fastapi import FastAPI
import httpx
from pydantic import BaseModel

from app.errors import (
    AppError,
    AuthError,
    ConflictError,
    ForbiddenError,
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


@pytest.mark.parametrize(
    "error_cls,expected_status",
    [
        (AppError, 500),
        (ValidationError, 400),
        (AuthError, 401),
        (ForbiddenError, 403),
        (NotFoundError, 404),
        (ConflictError, 409),
    ],
)
async def test_app_error_subclasses_return_unified_body(error_cls, expected_status):
    test_app = FastAPI()
    register_error_handlers(test_app)

    @test_app.get("/boom")
    async def boom():
        raise error_cls("SOME_CODE", "메시지")

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/boom")

    assert response.status_code == expected_status
    assert response.json() == {
        "error": {"code": "SOME_CODE", "message": "메시지", "field": None}
    }


async def test_body_validation_error_returns_field_and_code():
    test_app = FastAPI()
    register_error_handlers(test_app)

    class Body(BaseModel):
        name: str
        age: int

    @test_app.post("/thing")
    async def thing(body: Body):
        return {"ok": True}

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.post("/thing", json={"age": 3})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "SCHEMA_INVALID"
    assert body["error"]["field"] == "name"
    assert isinstance(body["error"]["message"], str)


async def test_malformed_json_error_has_null_field():
    test_app = FastAPI()
    register_error_handlers(test_app)

    class Body(BaseModel):
        name: str

    @test_app.post("/thing")
    async def thing(body: Body):
        return {"ok": True}

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.post(
            "/thing",
            content=b"{not valid json",
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "SCHEMA_INVALID"
    assert body["error"]["field"] is None


async def test_unknown_route_returns_unified_body():
    test_app = FastAPI()
    register_error_handlers(test_app)

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/nonexistent")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "HTTP_ERROR"
    assert body["error"]["field"] is None


async def test_unhandled_exception_returns_unified_body():
    test_app = FastAPI()
    register_error_handlers(test_app)

    @test_app.get("/boom")
    async def boom():
        raise RuntimeError("unexpected")

    transport = httpx.ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "서버 내부 오류가 발생했습니다",
            "field": None,
        }
    }
