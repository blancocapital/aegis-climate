from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from fastapi.middleware.cors import CORSMiddleware

from .storage.s3 import ensure_bucket

from .api.routes import router
from .api.schemas import build_api_error
from .core.middleware import correlation_middleware
from .core.request_id import generate_request_id

app = FastAPI(title="Aegis Climate MVP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.on_event("startup")
def startup_event():
    try:
        ensure_bucket()
    except Exception:
        # bucket creation best-effort
        pass


@app.on_event("startup")
def startup_event():
    try:
        ensure_bucket()
    except Exception:
        # bucket creation best-effort
        pass

app.middleware("http")(correlation_middleware)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None) or generate_request_id()
    payload = build_api_error(
        request_id=request_id,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": exc.errors()},
    )
    response = JSONResponse(status_code=422, content=payload)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def http_exception_handler(request: Request, exc: Exception):
    from fastapi import HTTPException

    request_id = getattr(request.state, "request_id", None) or generate_request_id()
    if isinstance(exc, HTTPException):
        detail = exc.detail
        code = "HTTP_ERROR"
        message = detail if isinstance(detail, str) else "HTTP error"
        details = detail if isinstance(detail, dict) else {"detail": detail}
        payload = build_api_error(request_id=request_id, code=code, message=message, details=details)
        response = JSONResponse(status_code=exc.status_code, content=payload)
    else:
        payload = build_api_error(
            request_id=request_id,
            code="INTERNAL_ERROR",
            message="Internal server error",
            details=None,
        )
        response = JSONResponse(status_code=500, content=payload)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/")
def root():
    return {"message": "Aegis Climate MVP API"}
