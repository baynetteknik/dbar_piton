"""add_working_mode_to_sites

Revision ID: 3c21b401b453
Revises: b7c54bd2d237
Create Date: 2026-07-19 21:51:58.536958

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c21b401b453'
down_revision: Union[str, Sequence[str], None] = 'b7c54bd2d237'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sites', sa.Column('working_mode', sa.String(length=50), server_default='local_master', nullable=False))


def downgrade() -> None:
    op.drop_column('sites', 'working_mode')
