"""create projects table

Revision ID: 0001
Revises: 
Create Date: 2026-11-02 22:38:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("git_remote", sa.Text(), server_default="", nullable=False),
        sa.Column("git_branch", sa.String(length=255), server_default="", nullable=False),
        sa.Column("instructions_path", sa.Text(), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("path", name="uq_projects_path"),
    )


def downgrade() -> None:
    op.drop_table("projects")
