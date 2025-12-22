.PHONY: dev backend frontend migrate seed install install-backend install-frontend

install: install-backend install-frontend

install-backend:
	pip install --no-cache-dir -r backend/requirements.txt

install-frontend:
	cd frontend && npm install

dev:
	docker compose -f infra/docker-compose.yml up --build

backend:
	uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm install && npm run dev -- --host 0.0.0.0

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python -m seed

test:
	cd backend && pytest
