"""clip resolved framing mode

Revision ID: 5b8e2d0c4a71
Revises: 7f2c41ab9d10
Create Date: 2026-11-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5b8e2d0c4a71"
down_revision: Union[str, Sequence[str], None] = "7f2c41ab9d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("clips", schema=None) as batch_op:
        batch_op.add_column(sa.Column("framing_mode", sa.String(length=30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("clips", schema=None) as batch_op:
        batch_op.drop_column("framing_mode")
