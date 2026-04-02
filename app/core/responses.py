from typing import Any, Optional
from pydantic import BaseModel
from fastapi.responses import JSONResponse

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[list[str]] = None
    code: Optional[str] = None

def ok(data: Any = None, message: str = "Success") -> APIResponse:
    return APIResponse(success=True, message=message, data=data)

def fail(message: str, errors: list[str] = None, code: str = None) -> APIResponse:
    return APIResponse(success=False, message=message, errors=errors, code=code)
