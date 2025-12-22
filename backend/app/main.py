from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from .storage.s3 import ensure_bucket

from .api.routes import router
from .core.middleware import correlation_middleware

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

app.middleware("http")(correlation_middleware)
app.include_router(router)


@app.get("/")
def root():
    return {"message": "Aegis Climate MVP API"}
