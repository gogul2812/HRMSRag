# Admin Config Service Dockerfile (service-local entrypoint)
# Canonical build context is the monorepo root; see also:
#   infra/docker/Dockerfile.admin-config-service
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash appuser

COPY shared-libs/schemas /shared-libs/schemas
COPY shared-libs/auth-middleware /shared-libs/auth-middleware
COPY shared-libs/observability /shared-libs/observability
COPY services/admin-config-service/pyproject.toml /app/pyproject.toml
COPY services/admin-config-service/app /app/app

RUN pip install --no-cache-dir \
    -e /shared-libs/schemas \
    -e /shared-libs/auth-middleware \
    -e /shared-libs/observability \
    && pip install --no-cache-dir \
    "fastapi>=0.110.0,<1.0.0" \
    "uvicorn[standard]>=0.29.0" \
    "sqlalchemy[asyncio]>=2.0.28" \
    "asyncpg>=0.29.0" \
    "pydantic-settings>=2.3,<3" \
    "python-jose[cryptography]>=3.3.0"

USER appuser
EXPOSE 8002
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
