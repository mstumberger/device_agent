import logging
from typing import Optional

# Global registry of all Logger instances
_logger_instances: set['Logger'] = set()


class Logger:
    """
    Base class that provides logging capability to all inheriting classes.
    """

    def __init__(self, name: Optional[str] = None, level: Optional[str] = None):
        """
        Initialize logger for this class.

        Args:
            name: Logger name (defaults to class module name)
            level: Initial log level (defaults to from config/env)
        """
        self._logger = logging.getLogger(name or self.__class__.__name__)
        if level:
            self._logger.setLevel(getattr(logging, level.upper()))
        # Register this instance for global level changes
        _logger_instances.add(self)

    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance."""
        return self._logger

    def debug(self, msg: str, *args, **kwargs):
        """Log debug message."""
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log info message."""
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message."""
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log error message."""
        self._logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Log critical message."""
        self._logger.critical(msg, *args, **kwargs)

    def set_level(self, level: str):
        """Change log level at runtime for this instance."""
        self._logger.setLevel(getattr(logging, level.upper()))

    def get_level(self) -> str:
        """Get current log level."""
        return logging.getLevelName(self._logger.level)

    @classmethod
    def set_all_levels(cls, level: str):
        """Change log level for all Logger instances at runtime."""
        numeric_level = getattr(logging, level.upper())
        for instance in _logger_instances:
            instance._logger.setLevel(numeric_level)
