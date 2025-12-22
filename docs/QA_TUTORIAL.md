# QA Tutorial

This guide describes how to run and debug the Playwright end-to-end harness that exercises ingestion, geocode/quality, hazard overlays, rollups, and breach governance.

## Prerequisites
- Docker + Docker Compose
- Node.js 18+
- Playwright browsers installed once per machine: `cd frontend && npx playwright install`

## One-command QA
From the repo root run:

```
make qa
```

The target:
1. Starts the full stack (`docker compose -f infra/docker-compose.yml up -d --build`).
2. Waits for the API and frontend to be reachable.
3. Runs migrations and seeds demo data.
4. Installs frontend deps if needed.
5. Executes `npm run test:e2e` headless against `http://localhost:5173`.
6. Leaves artifacts in the repo root:
   - `qa-results.json` (JSON summary reporter)
   - `playwright-report/` (HTML report)
   - `test-results/` (traces, screenshots, videos)

## Running E2E manually
- Ensure the stack is running (via `make dev` or your own deployment) and migrations/seeds are applied.
- Run the suite: `cd frontend && npm run test:e2e`
- Override the target URL with `PLAYWRIGHT_BASE_URL=https://your-env` if needed.

## Tests included
The suite (`frontend/tests/e2e/full-flow.spec.ts`) runs serially:
1. **Core happy-path ingestion + governance**: login, upload/mapping/validate/commit using `frontend/tests/fixtures/exposure_e2e.csv`, verify exposure detail/locations, runs, exceptions, audit log, and create a threshold rule.
2. **Geocode + quality run**: triggers geocode/quality from exposure detail and waits for completion.
3. **Hazard dataset upload + overlay**: creates a hazard dataset, uploads `frontend/tests/fixtures/hazard_demo.geojson`, creates an overlay, and waits for overlay status.
4. **Rollups + drilldown**: saves a rollup config, runs a rollup (optionally linking overlay result IDs), and performs a drilldown request.
5. **Thresholds + breaches end-to-end**: runs breach evaluation for the rollup result, then updates breach statuses to ACKED/RESOLVED.

## Debugging
- Headed mode: `cd frontend && npm run test:e2e:headed`
- Show a specific trace: `cd frontend && npx playwright show-trace ../test-results/<trace.zip>`
- Live debug inspector: `cd frontend && npx playwright test --debug`
- To re-run a single test: `cd frontend && npx playwright test tests/e2e/full-flow.spec.ts -g "Rollups"`

## Data fixtures
- `frontend/tests/fixtures/exposure_e2e.csv`: 3-location exposure with US (CA) and Canada (BC) points for overlay matching.
- `frontend/tests/fixtures/hazard_demo.geojson`: two polygons (HIGH over Northern CA, LOW over BC) used to validate overlay/rollup/breach flows.

## Console error policy
The tests fail on unexpected browser console errors. Known benign messages are allowlisted; add new allowlisted strings in `frontend/tests/e2e/helpers.ts` only when necessary.
