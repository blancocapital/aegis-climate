QA Report

WARNING: Alembic revision IDs were shortened for stability; no staged/prod DB usage notes were found in docs, so verify any non-local environments before upgrading.

Environment
- Host: local dev machine, docker compose stack (api/worker/postgres/redis/minio/frontend)
- Base URL: http://localhost:8000
- Auth: admin@demo.com / password (tenant_id: demo)

Commands and Results
- git status -sb (repo dirty; see "Changes Applied")
- cd backend && python3 -m pytest -q -> 72 passed
- docker compose -f infra/docker-compose.yml down -v || true
- docker compose -f infra/docker-compose.yml up -d --build
- make migrate (after fixes below) -> success, schema created
- make seed -> success
- make qa -> PASS (pytest + migrations + seed + qa_smoke)
- docker compose -f infra/docker-compose.yml ps -> all services up
- cd backend && python3 -m scripts.qa_smoke -> PASS (see Smoke Tests)
- cd backend && python3 -m pytest -q -> 72 passed

Smoke Tests (backend/scripts/qa_smoke.py)
- GET /health -> 200, X-Request-ID present (example: 860c038f-cd99-47d6-b27a-3a0dd3634bff)
- POST /auth/login -> 200
- POST /underwriting/packet (address-only) -> 200, keys present: property/hazards/resilience/provenance/quality/decision/explainability
- POST /resilience/score (address-only) -> 200 with hazards/result/data_quality/explainability
- POST /property-profiles/resolve twice -> reused cached/in-progress profile (no duplicate run)
- Exposure pipeline: /uploads -> /validate -> /commit -> exposure_version_id created
- POST /resilience-scores twice -> idempotent (EXISTING_* on repeat), status SUCCEEDED
- GET /resilience-scores/{id}/summary -> OK, buckets present
- GET /resilience-scores/{id}/disclosure -> OK, bucket_counts + bucket_tiv present
- GET /resilience-scores/{id}/items -> OK, keyset after_id works
- GET /resilience-scores/{id}/export.csv -> header + data row verified
- Run lifecycle: /runs/{id}/cancel invoked; retry attempted only if still CANCELLED

Logs Captured
- qa_api.log
- qa_worker.log
- qa_db.log (postgres service)

Changes Applied (Fixes)
- Makefile: fixed QA target indentation (tabs) so make migrate/seed and make qa work
- backend/alembic/env.py: removed manual alembic_version creation that opened an external transaction and caused migrations to roll back
- Shortened alembic revision IDs to <=32 chars and updated down_revision references:
  - 0007_hazard_registry_overlay (from 0007_hazard_registry_and_overlays)
  - 0018_resilience_hazard_ver
  - 0019_property_enrich_enum
  - 0021_res_score_request_fp
  - 0026_res_policy_link
  - Updated dependent revisions (0008, 0020, 0022)
- Added backend/scripts/qa_smoke.py (deterministic smoke tests)

Skipped
- Frontend E2E (make qa) not run to avoid Playwright setup churn; API smoke tests used as gate

Remaining Risks / Notes
- Cancel/retry is racey for fast runs; retry skipped if run transitions to SUCCEEDED before retry call
- QA created seed exposure/locations in DB; safe for local dev but not automatically cleaned

Current Working Tree
- Repo remains dirty; see `git status -sb` for full list (includes policy pack work + QA fixes + logs)
