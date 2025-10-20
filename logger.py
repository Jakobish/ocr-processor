"""
Enterprise OCR Structured Logging System
Provides comprehensive logging with rotation, remote capabilities, and structured output
"""
import os
import logging
import logging.handlers
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import structlog
from structlog.dev import ConsoleRenderer
from structlog import JSONRenderer
import requests
import time
from config import config


class RemoteLogHandler(logging.Handler):
    """Custom handler for remote logging"""

    def __init__(self, remote_url: str, api_key: Optional[str] = None,
                 batch_size: int = 10, flush_interval: int = 30):
        super().__init__()
        self.remote_url = remote_url
        self.api_key = api_key
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.log_buffer = []
        self.last_flush = time.time()

        # Circuit breaker for remote logging
        self.circuit_breaker_failures = 0
        self.circuit_breaker_timeout = 60

    def emit(self, record):
        """Emit log record to remote service"""
        try:
            # Format log entry
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
                'thread': record.thread,
                'process': record.process,
            }

            # Add structured fields if available
            if hasattr(record, '__dict__'):
                for key, value in record.__dict__.items():
                    if key not in ['name', 'msg', 'args', 'levelname', 'levelno',
                                 'pathname', 'filename', 'module', 'exc_info',
                                 'exc_text', 'stack_info', 'lineno', 'funcName',
                                 'created', 'msecs', 'relativeCreated', 'thread',
                                 'threadName', 'processName', 'process', 'getMessage']:
                        log_entry[f"field_{key}"] = value

            self.log_buffer.append(log_entry)

            # Flush buffer if needed
            now = time.time()
            if (len(self.log_buffer) >= self.batch_size or
                now - self.last_flush >= self.flush_interval):
                self._flush_buffer()

        except Exception as e:
            self.circuit_breaker_failures += 1
            if self.circuit_breaker_failures >= 5:
                print(f"⚠️ Remote logging circuit breaker activated: {e}")

    def _flush_buffer(self):
        """Flush log buffer to remote service"""
        if not self.log_buffer:
            return

        try:
            headers = {'Content-Type': 'application/json'}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'

            payload = {
                'logs': self.log_buffer,
                'source': 'ocr-processor',
                'version': '2.0.0'
            }

            response = requests.post(
                self.remote_url,
                json=payload,
                headers=headers,
                timeout=5
            )

            if response.status_code == 200:
                self.log_buffer.clear()
                self.last_flush = time.time()
                self.circuit_breaker_failures = 0
            else:
                self.circuit_breaker_failures += 1

        except Exception as e:
            self.circuit_breaker_failures += 1
            print(f"❌ Remote logging failed: {e}")


class OCRLogManager:
    """Centralized logging management for OCR processing"""

    def __init__(self, config):
        self.config = config
        self.logger = None
        self._setup_structured_logging()

    def _setup_structured_logging(self):
        """Set up structured logging with processors"""
        # Configure structlog processors
        processors = [
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ]

        # Add JSON renderer for file logging
        if self.config.log_to_file:
            processors.append(JSONRenderer())
        else:
            processors.append(ConsoleRenderer())

        # Configure structlog
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Set up Python logging
        self._setup_python_logging()

        # Create main logger
        self.logger = structlog.get_logger("ocr.processor")

    def _setup_python_logging(self):
        """Set up Python standard logging"""
        # Clear existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Set log level
        log_level = getattr(logging, self.config.log_level.upper())
        root_logger.setLevel(log_level)

        # Create formatters
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

        # File handler with rotation
        if self.config.log_to_file:
            self._setup_file_logging(root_logger, log_level)

        # Remote logging handler
        if self.config.enable_remote_logging and self.config.remote_log_url:
            remote_handler = RemoteLogHandler(self.config.remote_log_url)
            remote_handler.setLevel(log_level)
            root_logger.addHandler(remote_handler)

    def _setup_file_logging(self, root_logger: logging.Logger, log_level: int):
        """Set up file logging with rotation"""
        log_dir = Path(self.config.log_directory)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Main log file with rotation
        main_log_file = log_dir / "ocr_processor.log"
        file_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )

        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

        # Separate error log file
        error_log_file = log_dir / "ocr_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)

        # Performance log file
        perf_log_file = log_dir / "ocr_performance.log"
        perf_handler = logging.handlers.RotatingFileHandler(
            perf_log_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=2
        )
        perf_handler.setLevel(logging.INFO)
        perf_handler.addFilter(lambda record: record.levelno >= logging.INFO)
        root_logger.addHandler(perf_handler)

    def get_logger(self, name: str):
        """Get a structured logger instance"""
        return structlog.get_logger(name)

    def log_processing_start(self, job_id: str, file_path: str, mode: str, **kwargs):
        """Log processing start event"""
        if self.logger is not None:
            self.logger.info(
                "Processing started",
                job_id=job_id,
                file_path=file_path,
                mode=mode,
                event_type="processing_start",
                **kwargs
            )

    def log_processing_complete(self, job_id: str, file_path: str, success: bool,
                              processing_time: float, **kwargs):
        """Log processing completion event"""
        if self.logger is not None:
            self.logger.info(
                "Processing completed",
                job_id=job_id,
                file_path=file_path,
                success=success,
                processing_time=processing_time,
                event_type="processing_complete",
                **kwargs
            )

    def log_error(self, error: Exception, context: Dict[str, Any], **kwargs):
        """Log error with context"""
        if self.logger is not None:
            self.logger.error(
                "Error occurred",
                error=str(error),
                error_type=type(error).__name__,
                event_type="error",
                **context,
                **kwargs
            )

    def log_performance_metric(self, operation: str, duration: float,
                              file_size: Optional[int] = None, **kwargs):
        """Log performance metrics"""
        if self.logger is not None:
            # Also log to performance-specific logger using structlog
            perf_logger = structlog.get_logger("ocr.performance")

            perf_logger.info(
                f"Performance: {operation}",
                operation=operation,
                duration=duration,
                file_size=file_size,
                **kwargs
            )

    def log_batch_operation(self, operation: str, total_files: int,
                           success_count: int, failure_count: int, **kwargs):
        """Log batch operation statistics"""
        if self.logger is not None:
            self.logger.info(
                "Batch operation completed",
                operation=operation,
                total_files=total_files,
                success_count=success_count,
                failure_count=failure_count,
                success_rate=success_count / total_files if total_files > 0 else 0,
                event_type="batch_complete",
                **kwargs
            )

    def log_system_info(self):
        """Log system information for debugging"""
        import platform
        import psutil

        system_info = {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'cpu_count': os.cpu_count(),
            'memory_total': psutil.virtual_memory().total if psutil else 'unknown',
            'config': {
                'default_language': self.config.default_language,
                'default_mode': self.config.default_mode,
                'max_concurrent_jobs': self.config.max_concurrent_jobs,
            }
        }

        if self.logger is not None:
            self.logger.info(
                "System information",
                event_type="system_info",
                **system_info
            )

    def get_log_files(self) -> Dict[str, Path]:
        """Get paths to all log files"""
        log_dir = Path(self.config.log_directory)
        return {
            'main': log_dir / "ocr_processor.log",
            'errors': log_dir / "ocr_errors.log",
            'performance': log_dir / "ocr_performance.log"
        }

    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old log files"""
        log_dir = Path(self.config.log_directory)

        if not log_dir.exists():
            return

        cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)

        for log_file in log_dir.glob("*.log*"):
            try:
                if log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
                    if self.logger is not None:
                        self.logger.info(
                            "Cleaned up old log file",
                            file_path=str(log_file),
                            event_type="log_cleanup"
                        )
            except Exception as e:
                if self.logger is not None:
                    self.logger.warning(
                        "Failed to cleanup log file",
                        file_path=str(log_file),
                        error=str(e),
                        event_type="log_cleanup_error"
                    )


# Context manager for operation timing
class OperationTimer:
    """Context manager for timing operations"""

    def __init__(self, logger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(
            "Operation started",
            operation=self.operation,
            event_type="operation_start",
            **self.context
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
        else:
            duration = 0.0

        if exc_type:
            self.logger.error(
                "Operation failed",
                operation=self.operation,
                duration=duration,
                error=str(exc_val),
                event_type="operation_error",
                **self.context
            )
        else:
            self.logger.debug(
                "Operation completed",
                operation=self.operation,
                duration=duration,
                event_type="operation_complete",
                **self.context
            )


def get_logger(name: str = "ocr.processor"):
    """Get a configured logger instance"""
    return structlog.get_logger(name)


def log_operation(operation: str, **context):
    """Decorator for logging operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(f"ocr.processor.{func.__name__}")

            with OperationTimer(logger, operation, **context):
                return func(*args, **kwargs)

        return wrapper
    return decorator


# Global logger manager instance
try:
    log_manager = OCRLogManager(config)
except Exception as e:
    print(f"Logger initialization failed ({type(e).__name__}): {e}\n"
          "Possible causes: misconfigured 'config', missing dependencies, or file permission issues. "
          "Check your configuration and environment.")
    log_manager = None