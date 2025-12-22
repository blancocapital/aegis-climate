# Aegis Climate MVP

Reference implementation scaffold for the climate risk control tower MVP.

## Structure
- `backend/`: FastAPI app with placeholder endpoints and auth middleware.
- `frontend/`: React + Vite minimal UI covering required workflows.
- `infra/docker-compose.yml`: local stack (Postgres/PostGIS, Redis, MinIO, API, frontend).
- `docs/`: source requirements plus derived engineering docs.

## Quickstart
```bash
# start full stack (local dev)
make dev
```
Backend available at http://localhost:8000, frontend at http://localhost:5173.

### Run services individually
```bash
# install dependencies
make install

# start backend only
make backend

# start frontend only (requires npm registry access)
make frontend
```

> Note: npm installs may require outbound registry access; if blocked, configure an allowed mirror or install packages offline before running `make frontend`.

## Notes
- This scaffold emphasizes endpoints and artifacts defined in the MVP technical specification.
- Database migrations, Celery workers, and seeds are placeholders to be completed in follow-on iterations.

## Git remote
- `origin` is configured to point at `https://github.com/aegis-climate/aegis-climate.git` for pushing to the GitHub repository.
- To verify, run `git remote -v`.
- You will need appropriate GitHub credentials (token or SSH deploy key) in this environment to complete a `git push`; if your network blocks outbound GitHub traffic (e.g., CONNECT 403), configure an allowed proxy or perform the push from another environment.
