import uuid
from typing import Callable

from fastapi import Request, Response


async def correlation_middleware(request: Request, call_next: Callable) -> Response:
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response
