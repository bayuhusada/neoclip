"""clip caption font size

Revision ID: 9c1d4f6a2b83
Revises: 5b8e2d0c4a71
Create Date: 2026-11-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c1d4f6a2b83"
down_revision: Union[str, Sequence[str], None] = "5b8e2d0c4a71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("clips", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("caption_size", sa.Float(), nullable=False, server_default="1.0")
        )


def downgrade() -> None:
    with op.batch_alter_table("clips", schema=None) as batch_op:
        batch_op.drop_column("caption_size")
