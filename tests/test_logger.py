import structlog

from src.core.logger import setup_logging


def test_logger_setup(tmp_path):
    """Verify structlog initialization, file creation, and structured output formatting."""
    log_dir = tmp_path / "logs"
    setup_logging(log_dir=str(log_dir), log_level="DEBUG")

    # Verify log folder creation
    assert log_dir.exists()

    # Log structured message
    logger = structlog.get_logger("test_logger")
    logger.info("Test logging message", detail="context_value")

    # Verify log file is created and populated with formatted output
    log_file = log_dir / "app.log"
    assert log_file.exists()

    with open(log_file, encoding="utf-8") as f:
        log_content = f.read()

    assert "Test logging message" in log_content
    assert "context_value" in log_content
    assert "test_logger" in log_content
    assert "info" in log_content
