class BackupEngineError(Exception):
    """Base exception for all backup engine errors."""

    pass


class ConfigParseError(BackupEngineError):
    """Raised when parsing CMS PHP configuration files fails."""

    pass


class BackupError(BackupEngineError):
    """Raised when database or file backup operations fail."""

    pass


class MigrationError(BackupEngineError):
    """Raised when migration (SFTP or remote command execution) fails."""

    pass


class SchedulerError(BackupEngineError):
    """Raised when OS Task Scheduler integration fails."""

    pass
