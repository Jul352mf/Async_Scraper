"""Structured logging configuration using structlog."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import structlog

from scraper.core.config import get_config


class ColoredRenderer:
    """Custom colored renderer for console output."""
    
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
        "RESET": "\033[0m",       # Reset
    }
    
    def __call__(self, logger, method_name, event_dict):
        level = event_dict.get("level", "INFO").upper()
        color = self.COLORS.get(level, "")
        reset = self.COLORS["RESET"]
        
        timestamp = event_dict.get("timestamp", "")
        logger_name = event_dict.get("logger", "")
        message = event_dict.get("event", "")
        
        # Format additional fields
        extra_fields = {k: v for k, v in event_dict.items() 
                       if k not in ["timestamp", "level", "logger", "event"]}
        extra_str = " ".join(f"{k}={v}" for k, v in extra_fields.items()) if extra_fields else ""
        
        formatted = f"{timestamp} - {color}{level:8}{reset} - {logger_name} - {message}"
        if extra_str:
            formatted += f" - {extra_str}"
        
        return formatted


def setup_logging(config: Optional[Dict[str, Any]] = None) -> None:
    """Setup structured logging with the given configuration."""
    if config is None:
        config = get_config().logging.model_dump()
    
    # Create logs directory if file logging is enabled
    if config.get("file_enabled", True):
        log_file_path = Path(config.get("file_path", "logs/scraper.log"))
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, config.get("level", "INFO")),
    )
    
    # Configure structlog processors
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Add console renderer for development
    if config.get("debug", False):
        processors.append(ColoredRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )
    
    # Setup file handler if enabled
    if config.get("file_enabled", True):
        file_handler = logging.handlers.RotatingFileHandler(
            config.get("file_path", "logs/scraper.log"),
            maxBytes=config.get("max_file_size", 10485760),  # 10MB
            backupCount=config.get("backup_count", 5),
        )
        
        file_formatter = logging.Formatter(
            config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        file_handler.setFormatter(file_formatter)
        
        # Add file handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)


def get_logger(name: str, **initial_context) -> structlog.stdlib.BoundLogger:
    """Get a structured logger with optional initial context."""
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = get_logger(self.__class__.__name__)
    
    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get the logger instance."""
        return self._logger
    
    def log_debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._logger.debug(message, **kwargs)
    
    def log_info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._logger.info(message, **kwargs)
    
    def log_warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._logger.warning(message, **kwargs)
    
    def log_error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self._logger.error(message, **kwargs)
    
    def log_critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self._logger.critical(message, **kwargs)


class PerformanceLogger:
    """Logger for performance metrics and timing."""
    
    def __init__(self, name: str = "performance"):
        self.logger = get_logger(name)
    
    def log_timing(self, operation: str, duration: float, **context) -> None:
        """Log timing information."""
        self.logger.info(
            f"Operation completed: {operation}",
            duration=duration,
            operation=operation,
            **context
        )
    
    def log_throughput(self, operation: str, count: int, duration: float, **context) -> None:
        """Log throughput metrics."""
        rate = count / duration if duration > 0 else 0
        self.logger.info(
            f"Throughput: {operation}",
            count=count,
            duration=duration,
            rate=rate,
            operation=operation,
            **context
        )
    
    def log_memory_usage(self, operation: str, memory_mb: float, **context) -> None:
        """Log memory usage."""
        self.logger.info(
            f"Memory usage: {operation}",
            memory_mb=memory_mb,
            operation=operation,
            **context
        )
    
    def log_cache_stats(self, cache_name: str, hits: int, misses: int, **context) -> None:
        """Log cache statistics."""
        total = hits + misses
        hit_rate = hits / total if total > 0 else 0
        self.logger.info(
            f"Cache stats: {cache_name}",
            hits=hits,
            misses=misses,
            total=total,
            hit_rate=hit_rate,
            cache_name=cache_name,
            **context
        )


# Initialize logging on import
try:
    setup_logging()
except Exception as e:
    # Fallback to basic logging if setup fails
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).warning(f"Failed to setup structured logging: {e}")


# Export commonly used functions
__all__ = ["setup_logging", "get_logger", "LoggerMixin", "PerformanceLogger"]