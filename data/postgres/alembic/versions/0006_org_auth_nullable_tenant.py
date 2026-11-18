"""org auth: nullable tenant for super_admin, user name, org timestamps

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("created_by", sa.UUID(), nullable=True),
    )

    op.add_column(
        "users",
        sa.Column("full_name", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Super Admin has no organization (tenant_id NULL)
    op.alter_column("users", "tenant_id", existing_type=sa.UUID(), nullable=True)

    # Recreate unique (tenant_id, email) — Postgres treats NULLs as distinct
    op.drop_index("ix_users_tenant_email", table_name="users")
    op.create_index(
        "ix_users_tenant_email",
        "users",
        ["tenant_id", "email"],
        unique=True,
    )
    # Platform-wide unique email for super_admins (tenant_id IS NULL)
    op.create_index(
        "ix_users_super_admin_email",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_super_admin_email", table_name="users")
    op.drop_index("ix_users_tenant_email", table_name="users")
    # Cannot easily re-add NOT NULL if nulls exist — set orphan rows first
    op.execute("DELETE FROM users WHERE tenant_id IS NULL")
    op.alter_column("users", "tenant_id", existing_type=sa.UUID(), nullable=False)
    op.create_index(
        "ix_users_tenant_email",
        "users",
        ["tenant_id", "email"],
        unique=True,
    )
    op.drop_column("users", "updated_at")
    op.drop_column("users", "full_name")
    op.drop_column("tenants", "created_by")
    op.drop_column("tenants", "updated_at")
