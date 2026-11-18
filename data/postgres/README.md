# data/postgres

**Technology:** Alembic, SQLAlchemy, PostgreSQL 16

## Purpose

This directory contains all Alembic migration scripts for the platform's
relational database. It is the single source of truth for every table schema.

### Why Alembic?

- Migrations are versioned, incremental, and reproducible.
- Running `alembic upgrade head` is idempotent — safe to run in CI/CD.
- Each migration is a self-contained Python file that can be reviewed in code
  review like any other code change.

### Directory structure (planned — Stage 1+)

```
postgres/
├── alembic.ini          # Alembic configuration
├── alembic/
│   ├── env.py           # reads DATABASE_URL_SYNC from env
│   ├── script.py.mako   # migration template
│   └── versions/        # one file per migration
│       ├── 0001_create_tenants.py
│       ├── 0002_create_users.py
│       ├── 0003_create_documents.py
│       ├── 0004_create_prompt_configs.py
│       ├── 0005_create_guardrail_policies.py
│       └── 0006_create_chat_sessions_and_messages.py
└── init/
    └── 00_extensions.sql    # pg extensions (pgvector if needed, uuid-ossp)
```

### Multi-tenancy note

Every table that holds tenant-specific data includes a `tenant_id UUID NOT NULL`
column. Row-level security (RLS) policies are added in Stage 10. At every stage
before that, `tenant_id` filtering is enforced in service queries.

### Running migrations

```bash
# From repo root:
make migrate

# Or directly:
cd data/postgres
alembic upgrade head
alembic downgrade -1    # rollback one step
alembic history         # show migration history
```
