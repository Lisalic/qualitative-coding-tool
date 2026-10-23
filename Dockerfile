# Backend image. Built on the deploy VM itself (Oracle Ampere, arm64) by
# deploy/docker-compose.yml; python:3.12-slim is multi-arch, and every
# dependency in backend/requirements.txt ships an aarch64 wheel.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY alembic.ini .
COPY backend backend

RUN useradd --system --uid 10001 app
USER app

EXPOSE 8000

# Run from /app (the repo root) so `backend.app.*` imports resolve. One
# worker only: background jobs run as in-process asyncio tasks, and a
# second worker couldn't see or cancel the first one's jobs.
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
