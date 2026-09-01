import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.sql import text

from src.core.database import GenericRepository
from src.core.models import BaseModel


# Define a test model subclassing BaseModel
class SampleItem(BaseModel):
    __tablename__ = "sample_items"
    name: Mapped[str] = mapped_column(String, nullable=False)


def test_generic_repo_operations(db_session):
    """Test standard CRUD and Soft Delete functionality of GenericRepository."""
    # Create the sample_items table dynamically in the test DB schema
    SampleItem.metadata.create_all(bind=db_session.bind)

    repo = GenericRepository(db_session, SampleItem)

    # 1. Save
    item = SampleItem(name="Item A")
    repo.save(item)
    assert item.id is not None
    assert item.version_id == 1

    # 2. Get by ID
    fetched = repo.get_by_id(item.id)
    assert fetched is not None
    assert fetched.name == "Item A"

    # 3. Get All
    all_items = repo.get_all()
    assert len(all_items) == 1

    # 4. Soft Delete
    deleted = repo.delete(item.id, soft_delete=True)
    assert deleted is True

    # Verify soft deleted item is filtered out by default
    assert len(repo.get_all()) == 0
    assert repo.get_by_id(item.id) is None

    # Verify physical record still exists in the DB
    physical = (
        db_session.query(SampleItem).filter(SampleItem.id == item.id).first()
    )
    assert physical is not None
    assert physical.is_deleted is True


def test_optimistic_locking(db_session):
    """Test that modifying a stale object raises StaleDataError due to version mismatch."""
    SampleItem.metadata.create_all(bind=db_session.bind)

    repo = GenericRepository(db_session, SampleItem)

    item = SampleItem(name="Locking Test")
    repo.save(item)

    # Retrieve object
    obj1 = (
        db_session.query(SampleItem).filter(SampleItem.id == item.id).first()
    )

    # Simulate concurrent modification in DB directly using a separate connection
    # so the local session does not automatically detect or fetch it on commit.
    with db_session.bind.connect() as conn:
        conn.execute(
            text(
                "UPDATE sample_items SET name = 'Modified Externally', version_id = version_id + 1 WHERE id = :id",
            ),
            {"id": item.id},
        )
        conn.commit()

    # Attempt to edit and save stale obj1
    obj1.name = "Modified Locally"
    with pytest.raises(StaleDataError):
        db_session.commit()


def test_schema_compatibility_migration(tmp_path):
    """Test that DatabaseManager automatically adds missing columns to existing SQLite tables."""
    import sqlite3

    from sqlalchemy import inspect

    from src.core.database import DatabaseManager
    from src.core.models import Quotation

    db_file = tmp_path / "test_migration.db"
    
    # Create legacy table missing company_id, exchange_rate, etc.
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        """
        CREATE TABLE quotations (
            id INTEGER PRIMARY KEY,
            quotation_number VARCHAR(100) NOT NULL,
            title VARCHAR(255),
            quotation_type VARCHAR(50) DEFAULT 'Quotation',
            status VARCHAR(50) DEFAULT 'draft',
            created_at DATETIME,
            updated_at DATETIME,
            is_deleted BOOLEAN DEFAULT 0,
            version_id INTEGER DEFAULT 1
        )
        """,
    )
    conn.commit()
    conn.close()

    # Initializing DatabaseManager should trigger _ensure_compatibility_columns
    db_mgr = DatabaseManager(db_path=str(db_file))
    
    inspector = inspect(db_mgr.engine)
    col_names = {col["name"] for col in inspector.get_columns("quotations")}
    
    assert "company_id" in col_names
    assert "exchange_rate" in col_names
    assert "payment_plan" in col_names
    assert "grand_total" in col_names

    # Test querying with ORM
    session = db_mgr.get_db()
    try:
        results = session.query(Quotation).all()
        assert results == []
    finally:
        session.close()


