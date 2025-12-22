FROM python:3.11-slim

WORKDIR /app

# Copy dependency manifest from backend context (build context is repo root)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and alembic assets
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/seed.py ./seed.py

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
