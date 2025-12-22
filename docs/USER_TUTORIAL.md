# User Tutorial

This guide walks through running the Aegis Climate MVP locally and exercising every major feature end-to-end.

## Prerequisites
- Docker + Docker Compose
- Node.js 18+ (only needed if you prefer running the frontend locally)
- Python 3.11+ (only if running migrations/seeds outside Docker)

## Startup
1. From the repo root, launch the stack: `make dev` (wraps `docker compose -f infra/docker-compose.yml up --build`).
2. Apply migrations and seed demo data: `make migrate` then `make seed`.
3. The frontend is served on `http://localhost:5173` and the API on `http://localhost:8000`.

### Login credentials
All demo users share password `password` and tenant `demo`:
- Admin: `admin@demo.com`
- Ops: `ops@demo.com`
- Analyst: `analyst@demo.com`
- Auditor: `auditor@demo.com`
- Read-only: `readonly@demo.com`

## End-to-end workflow

### 1) Ingest exposures
1. Navigate to **Ingestion** (landing page after login).
2. Upload `frontend/tests/fixtures/exposure_e2e.csv` (3 locations across CA/BC with lat/lon and TIV).
3. Click **Auto mapping** to populate mapping JSON, then **Save mapping**.
4. Click **Validate** and wait for the run status to reach `SUCCEEDED`. Confirm `Errors: 0` in the stats row.
5. Click **Commit**. On success you are redirected to the new exposure version detail page with the locations table populated.

### 2) Exposure versions, locations, and geocode
1. Open **Exposure Versions** to see the committed version.
2. Click the version row to view **Locations** (expect 3 rows).
3. Optional: click **Run geocode + quality** to trigger the enrichment run. A status badge appears; wait for `SUCCEEDED`.

### 3) Exceptions queue
1. Open **Exceptions**.
2. Select your exposure version from the dropdown.
3. Review validation issues or confirm the empty-state message when no exceptions exist.

### 4) Hazard datasets and overlays
1. Open **Hazard Datasets**.
2. Create a dataset (name + peril are required).
3. Upload `frontend/tests/fixtures/hazard_demo.geojson` as a version. Two polygons are provided (HIGH over CA, LOW over BC).
4. Open **Overlays**.
5. Select the exposure version, your dataset, and the uploaded dataset version.
6. Click **Start overlay** and wait for the overlay status to reach `SUCCEEDED`. The summary shows matched bands.

### 5) Rollups and drilldown
1. Open **Rollups**.
2. Create a rollup config with dimensions `country`, `hazard_band`, `lob` and measures `tiv_sum` + `location_count`.
3. Select the exposure version, the rollup config, and (optionally) enter the overlay result ID from the previous step in the overlay field.
4. Click **Start rollup** and wait for rows to populate.
5. Use the **Drilldown** input with `{}` or a specific rollup key JSON to view contributing locations.

### 6) Threshold rules and breaches
1. Open **Threshold Rules** and create a rule targeting `tiv_sum` with an operator such as `>` and a low value (e.g., `100000`).
2. Open **Breaches**. Select the rule, select the exposure version, and enter the rollup result ID from step 5.
3. Click **Run evaluation**. Breaches table rows appear; update statuses to **ACKED** and **RESOLVED** to confirm persistence.

### 7) Governance views
- **Runs**: confirms validate/commit/overlay/rollup/breach runs are registered.
- **Audit Log**: lists login, upload, commit, and breach status updates.

## Troubleshooting
- **401 Unauthorized**: token expired; log in again.
- **Commit disabled**: validation is still running or `Errors > 0`.
- **No overlay versions listed**: ensure the hazard dataset upload succeeded; refresh the Overlays page.
- **Rollup missing overlay impact**: include overlay result IDs in the rollup form to blend hazard enrichment.
- **Seed data missing**: rerun `make seed`.
- **Worker jobs stuck**: check Docker `worker` container logs.
