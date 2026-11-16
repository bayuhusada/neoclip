"""clip render template

Revision ID: d4b1c7e05a38
Revises: c9af4226bb4e
Create Date: 2026-11-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4b1c7e05a38"
down_revision: Union[str, Sequence[str], None] = "c9af4226bb4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("clips", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("template", sa.String(length=30), nullable=False, server_default="clean")
        )


def downgrade() -> None:
    with op.batch_alter_table("clips", schema=None) as batch_op:
        batch_op.drop_column("template")
