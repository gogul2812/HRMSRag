"""fix RLS for super_admin null tenant_id and public org reads

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users: allow platform Super Admin rows when GUC is unset
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON users
          FOR ALL
          USING (
            tenant_id = app_current_tenant_id()
            OR (
              tenant_id IS NULL
              AND app_current_tenant_id() IS NULL
            )
          )
          WITH CHECK (
            tenant_id = app_current_tenant_id()
            OR (
              tenant_id IS NULL
              AND app_current_tenant_id() IS NULL
            )
          )
        """
    )

    # Tenants: allow listing active orgs when GUC unset (login dropdown)
    op.execute("DROP POLICY IF EXISTS tenant_self_read ON tenants")
    op.execute(
        """
        CREATE POLICY tenant_self_read ON tenants
          FOR SELECT
          USING (
            id = app_current_tenant_id()
            OR app_current_tenant_id() IS NULL
          )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON users
          FOR ALL
          USING (tenant_id = app_current_tenant_id())
          WITH CHECK (tenant_id = app_current_tenant_id())
        """
    )
    op.execute("DROP POLICY IF EXISTS tenant_self_read ON tenants")
    op.execute(
        """
        CREATE POLICY tenant_self_read ON tenants
          FOR SELECT
          USING (id = app_current_tenant_id())
        """
    )
