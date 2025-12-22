from fastapi import FastAPI

from .storage.s3 import ensure_bucket

from .api.routes import router
from .core.middleware import correlation_middleware

app = FastAPI(title="Aegis Climate MVP")


@app.on_event("startup")
def startup_event():
    try:
        ensure_bucket()
    except Exception:
        # bucket creation best-effort
        pass

app.middleware("http")(correlation_middleware)
app.include_router(router)


@app.get("/")
def root():
    return {"message": "Aegis Climate MVP API"}
