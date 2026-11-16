"""clip hook overlay switch + duration

Revision ID: 4a7d2f1c8e60
Revises: 9c1d4f6a2b83
Create Date: 2026-11-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4a7d2f1c8e60"
down_revision: Union[str, Sequence[str], None] = "9c1d4f6a2b83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("clips", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "hook_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(
            sa.Column(
                "hook_duration", sa.Float(), nullable=False, server_default="3.0"
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("clips", schema=None) as batch_op:
        batch_op.drop_column("hook_duration")
        batch_op.drop_column("hook_enabled")
