-- =============================================================================
-- Postgres Initialisation Script
-- Runs automatically on first container start (docker-entrypoint-initdb.d)
-- =============================================================================
-- This script only enables extensions. All table schemas are managed by
-- Alembic migrations (data/postgres/alembic/versions/).
-- =============================================================================

-- UUID generation (used for all primary keys)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pg_trgm for BM25-style text search (used in hybrid retrieval)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- btree_gin for composite GIN indexes
CREATE EXTENSION IF NOT EXISTS btree_gin;
