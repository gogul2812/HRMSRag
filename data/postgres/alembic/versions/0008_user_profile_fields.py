"""user profile personal/professional fields

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("job_title", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("department", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("location", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "location")
    op.drop_column("users", "department")
    op.drop_column("users", "job_title")
    op.drop_column("users", "phone")
