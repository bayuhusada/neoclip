"""video youtube_url for caption assist

Revision ID: 8f3a1d5c7b20
Revises: 4a7d2f1c8e60
Create Date: 2026-11-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f3a1d5c7b20"
down_revision: Union[str, Sequence[str], None] = "4a7d2f1c8e60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("videos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("youtube_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("videos", schema=None) as batch_op:
        batch_op.drop_column("youtube_url")
