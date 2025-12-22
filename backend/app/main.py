from fastapi import FastAPI

from .api.routes import router
from .core.middleware import correlation_middleware

app = FastAPI(title="Aegis Climate MVP")

app.middleware("http")(correlation_middleware)
app.include_router(router)


@app.get("/")
def root():
    return {"message": "Aegis Climate MVP API"}
