"""Initial skeleton

Revision ID: 9c03b491eac2
Revises: 
Create Date: 2026-07-12 21:33:16.442913

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '9c03b491eac2'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
