# QA Tutorial

## Prereqs
- Docker + Docker Compose
- Node.js 18+
- Playwright browsers installed once per machine: `cd frontend && npx playwright install`

## Run Playwright locally
From the repo root:
1. Start services (includes API + worker): `docker compose -f infra/docker-compose.yml up -d --build`
2. Migrate + seed: `make migrate && make seed`
3. Run tests: `cd frontend && npm run test:e2e`

The suite runs headless against `http://localhost:5173`.
To target another URL, set `PLAYWRIGHT_BASE_URL`.

## One-command QA
- `make qa`

This spins up Docker services, migrates/seeds, builds the frontend, and runs Playwright headless.
The JSON report is written to `qa-results.json` in the repo root.

## Artifacts and reports
- JSON summary: `qa-results.json`
- Playwright artifacts (traces/screenshots/videos): `frontend/test-results`

## Run a single test
- `cd frontend && npx playwright test tests/e2e/app.spec.ts`

## Debugging failures
- Headed mode: `cd frontend && npm run test:e2e:headed`
- Trace on failure (default): open the trace from `frontend/test-results` with:
  `cd frontend && npx playwright show-trace test-results/<trace.zip>`
- Live debug: `cd frontend && npx playwright test --debug`

## CI usage
- Ensure the app is running (or set `PLAYWRIGHT_BASE_URL` to the deployed URL).
- Run `cd frontend && npm run test:e2e`.
- Archive `qa-results.json` and `frontend/test-results` as CI artifacts.
