# Minimal API image. Schema is applied by `alembic upgrade head` at start, then
# uvicorn serves the app. (Production hardening -- non-root, gunicorn workers,
# read-only fs -- comes in the Phase 6 ops pass.)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
