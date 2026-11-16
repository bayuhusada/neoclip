"""clip caption preset and framing fields

Revision ID: 7f2c41ab9d10
Revises: d4b1c7e05a38
Create Date: 2026-11-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f2c41ab9d10"
down_revision: Union[str, Sequence[str], None] = "d4b1c7e05a38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("clips", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "caption_preset", sa.String(length=30), nullable=False, server_default="modern_bold"
            )
        )
        batch_op.add_column(
            sa.Column(
                "caption_source", sa.String(length=20), nullable=False, server_default="estimated"
            )
        )
        batch_op.add_column(
            sa.Column(
                "camera_mode", sa.String(length=30), nullable=False, server_default="original"
            )
        )
        batch_op.add_column(sa.Column("framing", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("clips", schema=None) as batch_op:
        batch_op.drop_column("framing")
        batch_op.drop_column("camera_mode")
        batch_op.drop_column("caption_source")
        batch_op.drop_column("caption_preset")
