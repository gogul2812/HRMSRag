"""create prompt_configs and guardrail_policies

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prompt_configs",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "version", name="uq_prompt_configs_tenant_version"),
    )
    op.create_index("ix_prompt_configs_tenant_id", "prompt_configs", ["tenant_id"], unique=False)
    # At most one active prompt config per tenant (partial unique index)
    op.create_index(
        "uq_prompt_configs_tenant_active",
        "prompt_configs",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_table(
        "guardrail_policies",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "version", name="uq_guardrail_policies_tenant_version"),
    )
    op.create_index("ix_guardrail_policies_tenant_id", "guardrail_policies", ["tenant_id"], unique=False)
    op.create_index(
        "uq_guardrail_policies_tenant_active",
        "guardrail_policies",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_guardrail_policies_tenant_active", table_name="guardrail_policies")
    op.drop_index("ix_guardrail_policies_tenant_id", table_name="guardrail_policies")
    op.drop_table("guardrail_policies")
    op.drop_index("uq_prompt_configs_tenant_active", table_name="prompt_configs")
    op.drop_index("ix_prompt_configs_tenant_id", table_name="prompt_configs")
    op.drop_table("prompt_configs")
