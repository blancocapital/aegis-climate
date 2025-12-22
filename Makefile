.PHONY: dev backend frontend migrate seed install install-backend install-frontend qa

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
	@if docker compose -f infra/docker-compose.yml ps -q api > /dev/null 2>&1; then \
		docker compose -f infra/docker-compose.yml exec -T api alembic upgrade head; \
	else \
		cd backend && alembic upgrade head; \
	fi

seed:
	@if docker compose -f infra/docker-compose.yml ps -q api > /dev/null 2>&1; then \
		docker compose -f infra/docker-compose.yml exec -T api python -m seed; \
	else \
		cd backend && python -m seed; \
	fi

test:
	cd backend && pytest

qa:
        docker compose -f infra/docker-compose.yml up -d --build
        @echo "Waiting for services..."
        @for i in $$(seq 1 60); do \
                if curl -sf http://localhost:8000/health > /dev/null && curl -sf http://localhost:5173 > /dev/null; then \
                        echo "Services are ready."; \
                        break; \
                fi; \
                sleep 2; \
        done
        $(MAKE) migrate
        $(MAKE) seed
        cd frontend && npm install
        cd frontend && PLAYWRIGHT_BASE_URL=http://localhost:5173 npm run test:e2e
        @echo "Artifacts available in qa-results.json, playwright-report/, and test-results/"
