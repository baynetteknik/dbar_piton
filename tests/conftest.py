from collections.abc import Generator

import pytest
import responses
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.models import Base


@pytest.fixture
def mock_api() -> Generator[responses.RequestsMock, None, None]:
    """Provides a mocked requests container for HTTP requests."""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provides a clean in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_class = sessionmaker(bind=engine)
    session = session_class()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
