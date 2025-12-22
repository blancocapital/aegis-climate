# OPERATIONS

## Run locally
- Recommended: `docker compose -f infra/docker-compose.yml up --build` to start Postgres, Redis, MinIO, API, worker, and frontend.
- Backend only: `pip install -r backend/requirements.txt` then `uvicorn backend.app.main:app --reload` (requires local Postgres/Redis/MinIO env vars).
- Frontend: `cd frontend && npm install && npm run dev -- --host 0.0.0.0`.

## Database & storage
- Postgres + PostGIS on 5432 (compose).
- Redis on 6379.
- MinIO console on 9001; credentials set by compose env (default `minioadmin`).

## Migrations
- `make migrate` runs Alembic upgrade head (from backend directory). Ensure compose is running or DATABASE_URL is set.

## Seeding
- `make seed` seeds demo tenant and users with password `password`. Safe to re-run.

## Jobs
- Celery worker runs in compose `worker` service. Validation/commit/geocode/hazard overlay endpoints enqueue tasks using Redis broker.
- Hazard overlay uses PostGIS spatial functions; ensure migrations ran after enabling PostGIS extension.

## Troubleshooting
- Verify env vars (AEGIS_DATABASE_URL, AEGIS_MINIO_* , AEGIS_REDIS_URL) are consistent between api and worker.
