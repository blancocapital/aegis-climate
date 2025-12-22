# OPENAPI NOTES

- FastAPI auto-generates OpenAPI schema from routers in `backend/app/api/routes.py`.
- Correlation-ID middleware ensures `X-Correlation-ID` header present on responses.
- Auth: bearer JWT with claims `tenant_id`, `role`, `sub` (user_id). All endpoints expect Authorization header.
- Error schema: FastAPI default; TODO align to spec with structured errors and severity metadata.
