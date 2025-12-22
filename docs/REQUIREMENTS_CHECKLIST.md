# REQUIREMENTS CHECKLIST (MVP)

Derived from `docs/mvp-technical-specification.md` (source of truth), with alignment to PRD and roadmap where applicable.

## Core Architecture & NFR
- [ ] FastAPI backend with tenant-scoped JWT auth, RBAC, structured logs, correlation IDs.
- [ ] Postgres 15 + PostGIS for canonical data; Alembic migrations provided.
- [ ] Redis + Celery for background pipelines.
- [ ] MinIO (S3 compatible) for uploads, exports, validation artifacts, rollup outputs.
- [ ] Docker Compose one-command start for db/redis/minio/api/worker/frontend.
- [ ] Idempotency + determinism: runs reference immutable inputs/config/dataset versions and code_version.
- [ ] Observability: metrics for pipeline duration/failure, queue depth; health endpoint.

## Authentication & RBAC
- [ ] POST /auth/login issues JWT with tenant_id + role (ADMIN, OPS, ANALYST, AUDITOR, READ_ONLY).
- [ ] RBAC enforced on every endpoint per RBAC matrix.
- [ ] Tenant scoping enforced on every DB query.

## Exposure Onboarding
- [ ] POST /uploads returns upload_id + signed URL/storage reference; raw file stored in object storage.
- [ ] POST /uploads/{upload_id}/mapping creates/attaches versioned mapping_template.
- [ ] POST /uploads/{upload_id}/validate triggers validation job; returns summary + row_errors_uri.
- [ ] POST /uploads/{upload_id}/commit creates immutable exposure_version referencing upload + mapping.
- [ ] Validation includes severity ERROR/WARN/INFO; outputs row-level artifact.
- [ ] Canonical tables: location, account, policy; stored per exposure_version.

## Geocode & Quality Scoring
- [ ] Geocoding pipeline fills missing lat/lon from address using provider abstraction (real provider or deterministic stub).
- [ ] Store geocode method, confidence, provenance per location.
- [ ] Compute completeness/geocode/financial scores → overall quality tier (A/B/C) + reasons.
- [ ] Exceptions queue surfaces Tier C/low confidence/unresolved WARN/ERROR items.

## Hazard Registry & Overlays
- [ ] Entities: hazard_dataset, hazard_dataset_version (immutable), hazard_overlay_result, location_hazard_attribute.
- [ ] Support ingestion of at least one dataset type (GeoJSON/PostGIS polygons) into PostGIS.
- [ ] POST /hazard-overlays runs spatial join to populate standardized hazard attributes (category/band/percentile/score/source/method).
- [ ] Overlay summary/status endpoints available.

## Rollups & Breaches
- [ ] rollup_config CRUD (versioned) with dimensions/filters/measures.
- [ ] POST /rollups executes aggregation for exposure_version + overlays; stores results (table or Parquet) with checksum + storage_uri.
- [ ] GET /rollups/{id} returns metadata/data; GET /rollups/{id}/drilldown returns contributing locations/accounts.
- [ ] threshold_rule creation; POST /breaches/run evaluates rules vs rollup results deterministically.
- [ ] breach workflow: statuses OPEN → ACKED → RESOLVED; PATCH endpoint enforces transitions.

## Drift
- [x] POST /drift compares exposure_version A vs B keyed by external_location_id; classify NEW/REMOVED/MODIFIED with numeric deltas.
- [x] Aggregate drift by configured dimensions; export artifact to object storage; register run.
- [x] GET /drift/{id} summary; GET /drift/{id}/details detailed diffs.

## Governance
- [x] run registry for VALIDATION, GEOCODE, OVERLAY, ROLLUP, BREACH_EVAL, DRIFT with input_refs, config_refs, output_refs, code_version, checksums where applicable.
- [x] Lineage endpoint returns dependencies for any output (e.g., rollup_result → exposure_version + overlays + configs + runs + users + timestamps).
- [x] Audit events append-only for sensitive actions (login, role changes, mapping changes, exposure commit, hazard dataset version creation, threshold changes, breach status changes, exports, config changes).

## Frontend (React + Vite)
- [ ] Screens: Upload & Mapping; Validation summary + row error explorer; Exceptions queue; Accumulation dashboard (rollups + drilldown); Threshold builder + breach list (status updates); Drift report compare A vs B; Governance views (Versions/Runs/Lineage); Audit log viewer.
- [ ] Uses API endpoints with tenant-scoped auth; handles S3 uploads; displays validation artifacts and rollup results.

## Operations
- [ ] README + docs/OPERATIONS.md cover running services, migrations, seeds, jobs, troubleshooting.
- [ ] Seed script creates demo tenant/users/data and golden dataset for determinism tests.
- [ ] Makefile/scripts include migrate/seed/test commands.

## Testing
- [ ] Unit: mapping transforms, validation rules, quality scoring, overlay join, rollup aggregation, threshold evaluation, drift classification.
- [ ] Integration: API endpoints with tenant scoping + RBAC.
- [ ] Golden dataset determinism: pipeline run twice produces identical checksums for artifacts and aggregates.
