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

