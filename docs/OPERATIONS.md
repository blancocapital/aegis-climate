# OPERATIONS

## Run locally
- Install Python 3.11+ and Node 18+.
- Backend: `pip install -r backend/requirements.txt` then `uvicorn backend.app.main:app --reload`.
- Frontend: `cd frontend && npm install && npm run dev -- --host 0.0.0.0`.
- Compose (recommended): `docker compose -f infra/docker-compose.yml up --build`.

## Database & storage
- Postgres + PostGIS exposed on 5432 (compose).
- Redis on 6379.
- MinIO console on :9001; access key/password `minioadmin` for local only.

## Migrations
- Alembic migrations not yet added; placeholder `make migrate` prints TODO.

## Seeding
- `make seed` placeholder; to be replaced with script creating demo tenant/users/datasets.

## Jobs
- Background jobs (Celery) not yet wired; plan to trigger via API endpoints and queue in Redis.

## Troubleshooting
- Ensure Docker resources allow building images (backend/frontned).
- Check `X-Correlation-ID` header in responses for tracing.
