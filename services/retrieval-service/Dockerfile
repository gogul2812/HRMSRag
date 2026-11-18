FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash appuser

COPY shared-libs/schemas /shared-libs/schemas
COPY shared-libs/auth-middleware /shared-libs/auth-middleware
COPY shared-libs/observability /shared-libs/observability
COPY ai-core/embedding /ai-core/embedding
COPY ai-core/reranking /ai-core/reranking
COPY services/retrieval-service/pyproject.toml /app/pyproject.toml
COPY services/retrieval-service/app /app/app

RUN pip install --no-cache-dir \
    -e /shared-libs/schemas \
    -e /shared-libs/auth-middleware \
    -e /shared-libs/observability \
    -e /ai-core/embedding \
    -e /ai-core/reranking \
    && pip install --no-cache-dir \
    "fastapi>=0.110.0,<1.0.0" \
    "uvicorn[standard]>=0.29.0" \
    "qdrant-client>=1.9.0" \
    "pydantic-settings>=2.3,<3" \
    "python-jose[cryptography]>=3.3.0"

USER appuser
EXPOSE 8004
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
