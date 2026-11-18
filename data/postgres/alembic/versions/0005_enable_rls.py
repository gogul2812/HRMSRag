"""enable row-level security on tenant-scoped tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that carry tenant_id and must be isolated by RLS.
TENANT_TABLES = (
    "users",
    "documents",
    "prompt_configs",
    "guardrail_policies",
    "chat_sessions",
    "chat_messages",
    "feedback",
)


def upgrade() -> None:
    # Session GUC used by policies: SET LOCAL app.current_tenant_id = '<uuid>';
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_tenant_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        AS $$
          SELECT NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        $$;
        """
    )

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
              FOR ALL
              USING (tenant_id = app_current_tenant_id())
              WITH CHECK (tenant_id = app_current_tenant_id())
            """
        )

    # tenants table is catalog-level — readable when GUC matches for non-superusers
    # that need tenant metadata; inserts remain service-controlled.
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_self_read ON tenants")
    op.execute(
        """
        CREATE POLICY tenant_self_read ON tenants
          FOR SELECT
          USING (id = app_current_tenant_id())
        """
    )
    op.execute("DROP POLICY IF EXISTS tenant_service_write ON tenants")
    op.execute(
        """
        CREATE POLICY tenant_service_write ON tenants
          FOR ALL
          USING (app_current_tenant_id() IS NULL OR id = app_current_tenant_id())
          WITH CHECK (true)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_service_write ON tenants")
    op.execute("DROP POLICY IF EXISTS tenant_self_read ON tenants")
    op.execute("ALTER TABLE tenants NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY")

    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP FUNCTION IF EXISTS app_current_tenant_id()")
