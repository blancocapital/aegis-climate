from typing import Callable

from fastapi import Request, Response

from app.core.request_id import generate_request_id, reset_request_id, set_request_id

async def correlation_middleware(request: Request, call_next: Callable) -> Response:
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        correlation_id = generate_request_id()
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = generate_request_id()

    request.state.correlation_id = correlation_id
    request.state.request_id = request_id
    token = set_request_id(request_id)
    try:
        response = await call_next(request)
    finally:
        reset_request_id(token)
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Request-ID"] = request_id
    return response
