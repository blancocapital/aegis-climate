# User Tutorial

## Prereqs
- Docker + Docker Compose
- Node.js 18+
- Python 3.11+ (for local migrate/seed if you do not rely on Docker containers)

## One-command startup
- `make dev` (wraps `docker compose -f infra/docker-compose.yml up --build`)

## Migrate + seed
- `make migrate`
- `make seed`

## Login credentials
All demo users share password `password` and tenant `demo`:
- Admin: `admin@demo.com`
- Ops: `ops@demo.com`
- Analyst: `analyst@demo.com`
- Auditor: `auditor@demo.com`
- Read-only: `readonly@demo.com`

## End-to-end workflow (all available features)

### 1) Ingest exposures
1. Go to **Ingestion**.
2. Upload a CSV (use `sample_data/exposure_small.csv` to start). Ensure the file includes `external_location_id`, `tiv`, and at least one segmentation field (`lob` or `product_code`).
3. Click **Auto mapping** to populate the mapping JSON, then **Save mapping**.
4. Click **Validate** and wait for the status to reach `SUCCEEDED`.
5. Confirm **Errors: 0**, then click **Commit**.
6. You will be routed to the new exposure version detail.

### 2) Review exposure versions + locations
1. Open **Exposure Versions** to see all committed versions.
2. Click a version to view its **Locations** table.
3. Optional: run **Geocode + quality** from the detail page to populate quality tiers.

### 3) Exceptions queue
1. Open **Exceptions**.
2. Select an exposure version.
3. Review validation issues and data-quality exceptions (quality tier C / low geocode confidence).

### 4) Hazard datasets + overlays
1. Open **Hazard Datasets**.
2. Create a dataset (name + peril).
3. Upload a GeoJSON file to create a dataset version.
4. Open **Overlays**.
5. Select exposure version, dataset, and dataset version.
6. Click **Start overlay** and wait for `SUCCEEDED`.

### 5) Rollups + drilldown
1. Open **Rollups**.
2. Create a rollup config (dimensions + measures JSON).
3. Select an exposure version and rollup config, then **Start rollup**.
4. Inspect rollup rows and run **Drilldown** with a rollup key JSON.

### 6) Thresholds + breaches
1. Open **Threshold Rules**.
2. Create a rule (example JSON: `{ "metric": "tiv_sum", "operator": ">", "value": 1000000 }`).
3. Open **Breaches**.
4. Enter a rollup result ID and select a rule.
5. Click **Run evaluation**; update statuses to **ACKED** or **RESOLVED**.

### 7) Governance views
- **Runs**: inspect run registry (validation/commit/overlay/rollup/breach/drift).
- **Audit Log**: review immutable audit events (login, uploads, changes).

## Troubleshooting
- **401 Unauthorized**: token expired or missing; log in again.
- **422/400 during validate/commit**: mapping JSON invalid or missing required fields.
- **Commit disabled**: validation has `ERROR > 0` or validation has not finished.
- **No locations after commit**: source data missing `lob` or `product_code`.
- **CORS errors**: ensure `VITE_API_URL` matches the backend URL (default `http://localhost:8000`).
- **Validation/commit stuck**: confirm the Celery worker is running (Docker `worker` service).
- **No demo users**: run `make seed` again.
