import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("ccps")


class BusinessError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, errors: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.errors = errors or {}
        super().__init__(message)


def _error_body(message, errors=None):
    return {"success": False, "message": message, "errors": errors or {}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BusinessError)
    async def business_error_handler(request: Request, exc: BusinessError):
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.message, exc.errors))

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        errors = {}
        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"] if part not in ("body", "query", "path"))
            message = error["msg"].replace("Value error, ", "")
            errors.setdefault(field or "non_field_errors", []).append(message)
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=_error_body("Validation failed.", errors))

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("Something went wrong. Please try again later."),
        )
