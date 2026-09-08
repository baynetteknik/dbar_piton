"""roles table + extended user fields

Revision ID: e2b3c4d5f6a7
Revises: d1a2c3e4f5a6
Create Date: 2026-09-07 19:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2b3c4d5f6a7"
down_revision: Union[str, Sequence[str], None] = "d1a2c3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("permissions_json", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("full_name", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("email", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("phone", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("must_change_password", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("last_login_at", sa.String(length=25), nullable=True))
        batch.add_column(sa.Column("role_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        for col in ("role_id", "last_login_at", "must_change_password",
                    "phone", "email", "full_name"):
            batch.drop_column(col)
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")
