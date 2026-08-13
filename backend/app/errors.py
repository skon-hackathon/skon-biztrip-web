from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 500

    def __init__(self, code: str, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


class ValidationError(AppError):
    status_code = 400


class AuthError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


def _body(code: str, message: str, field: str | None) -> dict:
    return {"error": {"code": code, "message": message, "field": field}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.code, exc.message, exc.field),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = first.get("loc") or []
        field = str(location[-1]) if location else None
        return JSONResponse(
            status_code=422,
            content=_body("SCHEMA_INVALID", first.get("msg", "요청 형식이 올바르지 않습니다"), field),
        )
