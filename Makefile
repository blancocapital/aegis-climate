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
	cd backend && python3 -m pytest -q
	docker compose -f infra/docker-compose.yml up -d --build
	@echo "Waiting for services..."
	@ready=0; \
	for i in $$(seq 1 60); do \
		if curl -sf http://localhost:8000/health > /dev/null; then \
			ready=1; \
			echo "Services are ready."; \
			break; \
		fi; \
		sleep 2; \
	done; \
	if [ $$ready -ne 1 ]; then \
		echo "Services failed readiness checks."; \
		exit 1; \
	fi
	$(MAKE) migrate
	$(MAKE) seed
	cd backend && python3 -m scripts.qa_smoke
