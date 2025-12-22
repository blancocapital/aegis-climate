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

## Git remote and pushing to GitHub
- The repo no longer has a default `origin` configured. Set one explicitly for your GitHub project, for example:
  ```bash
  git remote add origin https://github.com/<your-username>/aegis-climate.git
  ```
- To push with a GitHub personal access token without exposing it in the shell history, create a temporary askpass helper:
  ```bash
  cat > /tmp/git-askpass.sh <<'"'"'EOF'"'"'
  #!/usr/bin/env bash
  echo "$GITHUB_PAT"
  EOF
  chmod 700 /tmp/git-askpass.sh
  GIT_ASKPASS=/tmp/git-askpass.sh GITHUB_PAT=<your-token> git push origin work
  ```
  Replace `<your-token>` with your PAT, and remove `/tmp/git-askpass.sh` afterward.
- If outbound GitHub access is blocked in this environment (e.g., CONNECT 403), perform the push from a network that allows GitHub traffic or through an approved proxy.
