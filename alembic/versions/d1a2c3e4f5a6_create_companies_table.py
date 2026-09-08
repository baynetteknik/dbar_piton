"""create_companies_table

Revision ID: d1a2c3e4f5a6
Revises: ca640f2d50c1
Create Date: 2026-09-07 19:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1a2c3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "ca640f2d50c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("short_name", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("company_type", sa.String(length=30), nullable=True),
        sa.Column("tax_office", sa.String(length=120), nullable=True),
        sa.Column("tax_office_code", sa.String(length=20), nullable=True),
        sa.Column("tax_number", sa.String(length=20), nullable=True),
        sa.Column("mersis_no", sa.String(length=25), nullable=True),
        sa.Column("trade_registry_no", sa.String(length=40), nullable=True),
        sa.Column("nace_code", sa.String(length=20), nullable=True),
        sa.Column("sgk_no", sa.String(length=40), nullable=True),
        sa.Column("founded_at", sa.String(length=10), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("district", sa.String(length=80), nullable=True),
        sa.Column("city", sa.String(length=80), nullable=True),
        sa.Column("postal_code", sa.String(length=15), nullable=True),
        sa.Column("country", sa.String(length=60), nullable=True),
        sa.Column("phone1", sa.String(length=30), nullable=True),
        sa.Column("phone2", sa.String(length=30), nullable=True),
        sa.Column("fax", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=120), nullable=True),
        sa.Column("accounting_email", sa.String(length=120), nullable=True),
        sa.Column("website", sa.String(length=120), nullable=True),
        sa.Column("kep_address", sa.String(length=120), nullable=True),
        sa.Column("authorized_person", sa.String(length=120), nullable=True),
        sa.Column("authorized_title", sa.String(length=80), nullable=True),
        sa.Column("authorized_phone", sa.String(length=30), nullable=True),
        sa.Column("e_invoice_enabled", sa.Boolean(), nullable=True),
        sa.Column("e_archive_enabled", sa.Boolean(), nullable=True),
        sa.Column("e_dispatch_enabled", sa.Boolean(), nullable=True),
        sa.Column("gib_alias", sa.String(length=80), nullable=True),
        sa.Column("integrator", sa.String(length=80), nullable=True),
        sa.Column("default_currency", sa.String(length=5), nullable=True),
        sa.Column("default_vat_rate", sa.Integer(), nullable=True),
        sa.Column("fiscal_year_start", sa.String(length=5), nullable=True),
        sa.Column("logo_base64", sa.Text(), nullable=True),
        sa.Column("stamp_base64", sa.Text(), nullable=True),
        sa.Column("bank_accounts_json", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_code", "companies", ["code"], unique=True)
    op.create_index("ix_companies_id", "companies", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_companies_code", table_name="companies")
    op.drop_index("ix_companies_id", table_name="companies")
    op.drop_table("companies")
