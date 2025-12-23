from typing import Any, Dict, Optional

from pydantic import BaseModel


class APIError(BaseModel):
    request_id: str
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class APIWarning(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


def build_api_error(
    request_id: str,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    error = APIError(request_id=request_id, code=code, message=message, details=details)
    return error.model_dump()
