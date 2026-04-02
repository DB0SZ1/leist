from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from app.core.responses import fail

class AppException(Exception):
    status_code: int = 500
    message: str = "Internal server error"
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = None, code: str = None, status_code: int = None):
        self.message = message or self.__class__.message
        self.code = code or self.__class__.code
        self.status_code = status_code or self.__class__.status_code

class AuthException(AppException):
    status_code = 401
    message = "Authentication required"
    code = "AUTH_REQUIRED"

class ForbiddenException(AppException):
    status_code = 403
    message = "Access denied"
    code = "FORBIDDEN"

class NotFoundException(AppException):
    status_code = 404
    message = "Resource not found"
    code = "NOT_FOUND"

class InsufficientCreditsException(AppException):
    status_code = 402
    message = "Insufficient credits"
    code = "INSUFFICIENT_CREDITS"

class PaystackException(AppException):
    status_code = 400
class UnverifiedEmailException(AppException):
    status_code = 403
    message = "Email not verified"
    code = "UNVERIFIED_EMAIL"
    def __init__(self, email: str):
        super().__init__(message=self.message, code=self.code, status_code=self.status_code)
        self.email = email

from fastapi.responses import RedirectResponse, JSONResponse

def setup_exception_handlers(app):
    @app.exception_handler(UnverifiedEmailException)
    async def unverified_email_handler(request: Request, exc: UnverifiedEmailException):
        if not request.url.path.startswith("/api/v1"):
            from urllib.parse import urlencode
            return RedirectResponse(url=f"/verify-email?{urlencode({'email': exc.email})}")
        return JSONResponse(status_code=exc.status_code, content=fail(exc.message, code=exc.code).model_dump())

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        if exc.status_code == 401 and not request.url.path.startswith("/api/v1"):
            return RedirectResponse(url="/login")
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(exc.message, code=exc.code).model_dump()
        )
