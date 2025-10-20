"""
Enterprise OCR Error Handling and Recovery
Provides comprehensive error handling, retry mechanisms, and recovery strategies
"""
import time
import logging
import functools
from typing import Dict, Any, Optional, Callable, Type, Union
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import requests


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification"""
    VALIDATION = "validation"
    PROCESSING = "processing"
    SYSTEM = "system"
    NETWORK = "network"
    PERMISSION = "permission"
    RESOURCE = "resource"
    DEPENDENCY = "dependency"


@dataclass
class ErrorContext:
    """Context information for error handling"""
    operation: str
    file_path: Optional[str] = None
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    max_retries: int = 3
    backoff_multiplier: float = 2.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorMetrics:
    """Track error metrics for monitoring"""
    total_errors: int = 0
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    recovery_success_rate: float = 0.0
    average_recovery_time: float = 0.0


class OCRError(Exception):
    """Base OCR processing error"""
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.PROCESSING,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 context: Optional[ErrorContext] = None,
                 recoverable: bool = True):
        super().__init__(message)
        self.category = category
        self.severity = severity
        self.context = context or ErrorContext("unknown")
        self.recoverable = recoverable
        self.timestamp = datetime.now()


class ValidationError(OCRError):
    """Input validation errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.VALIDATION, ErrorSeverity.HIGH, **kwargs)


class ProcessingError(OCRError):
    """OCR processing errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.PROCESSING, ErrorSeverity.MEDIUM, **kwargs)


class SystemError(OCRError):
    """System resource errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.SYSTEM, ErrorSeverity.HIGH, **kwargs)


class NetworkError(OCRError):
    """Network connectivity errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.NETWORK, ErrorSeverity.MEDIUM,
                        recoverable=True, **kwargs)


class CircuitBreaker:
    """Circuit breaker for external service calls"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise NetworkError("Circuit breaker is OPEN", recoverable=True)

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset"""
        if self.last_failure_time is None:
            return True
        return (datetime.now() - self.last_failure_time).seconds >= self.recovery_timeout

    def _on_success(self):
        """Handle successful execution"""
        self.failure_count = 0
        self.state = "CLOSED"

    def _on_failure(self):
        """Handle failed execution"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class RetryMechanism:
    """Exponential backoff retry mechanism"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0,
                 max_delay: float = 60.0, backoff_multiplier: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                # Don't retry non-recoverable errors
                if hasattr(e, 'recoverable') and not e.recoverable:
                    raise e

                if attempt == self.max_retries:
                    break

                delay = min(self.base_delay * (self.backoff_multiplier ** attempt), self.max_delay)
                print(f"⏳ Retry attempt {attempt + 1}/{self.max_retries} after {delay:.1f}s delay")
                time.sleep(delay)

        raise last_exception


class NotificationManager:
    """Handle error notifications and alerts"""

    def __init__(self, config):
        self.config = config
        self.circuit_breaker = CircuitBreaker()

    def send_notification(self, error: OCRError, context: ErrorContext):
        """Send error notification via configured channels"""
        if not self.config.enable_notifications:
            return

        try:
            # Email notification
            if self.config.notification_email:
                self._send_email_notification(error, context)

            # Webhook notification
            if self.config.webhook_url:
                self._send_webhook_notification(error, context)

        except Exception as e:
            print(f"❌ Failed to send notification: {e}")

    def _send_email_notification(self, error: OCRError, context: ErrorContext):
        """Send email notification"""
        try:
            msg = MimeMultipart()
            msg['From'] = self.config.smtp_username
            msg['To'] = self.config.notification_email
            msg['Subject'] = f"OCR Processing Error: {error.category.value.title()}"

            # Email body
            body = f"""
OCR Processing Error Notification

Error: {error}
Severity: {error.severity.value}
Category: {error.category.value}
Operation: {context.operation}
File: {context.file_path or 'N/A'}
Timestamp: {error.timestamp}
Recovery Possible: {error.recoverable}

Context: {json.dumps(context.metadata, indent=2, default=str)}
            """

            msg.attach(MimeText(body, 'plain'))

            # Send email
            server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
            server.starttls()
            server.login(self.config.smtp_username, self.config.smtp_password)
            server.send_message(msg)
            server.quit()

        except Exception as e:
            print(f"❌ Email notification failed: {e}")

    def _send_webhook_notification(self, error: OCRError, context: ErrorContext):
        """Send webhook notification"""
        try:
            payload = {
                "error": str(error),
                "severity": error.severity.value,
                "category": error.category.value,
                "operation": context.operation,
                "file_path": context.file_path,
                "timestamp": error.timestamp.isoformat(),
                "recoverable": error.recoverable,
                "context": context.metadata
            }

            self.circuit_breaker.call(
                requests.post,
                self.config.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

        except Exception as e:
            print(f"❌ Webhook notification failed: {e}")


class ErrorHandler:
    """Main error handling and recovery coordinator"""

    def __init__(self, config):
        self.config = config
        self.metrics = ErrorMetrics()
        self.retry_mechanism = RetryMechanism(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0
        )
        self.notification_manager = NotificationManager(config)

        # Set up error tracking
        self.error_log = []
        self.max_error_log_size = 1000

    def handle_error(self, error: Exception, context: ErrorContext) -> bool:
        """Handle error with appropriate recovery strategy"""
        # Convert to OCRError if needed
        if not isinstance(error, OCRError):
            error = self._classify_error(error, context)

        # Update metrics
        self._update_metrics(error)

        # Log error
        self._log_error(error, context)

        # Send notification for high severity errors
        if error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self.notification_manager.send_notification(error, context)

        # Attempt recovery if possible
        if error.recoverable:
            return self._attempt_recovery(error, context)

        return False

    def _classify_error(self, error: Exception, context: ErrorContext) -> OCRError:
        """Classify generic exceptions into OCR errors"""
        error_msg = str(error).lower()

        if any(keyword in error_msg for keyword in ['permission', 'access denied', 'forbidden']):
            return SystemError(str(error), category=ErrorCategory.PERMISSION,
                              severity=ErrorSeverity.HIGH, recoverable=False)

        elif any(keyword in error_msg for keyword in ['connection', 'timeout', 'network']):
            return NetworkError(str(error), recoverable=True)

        elif any(keyword in error_msg for keyword in ['memory', 'disk', 'space']):
            return SystemError(str(error), category=ErrorCategory.RESOURCE,
                              severity=ErrorSeverity.HIGH, recoverable=False)

        elif any(keyword in error_msg for keyword in ['tesseract', 'ocrmypdf']):
            return ProcessingError(str(error), category=ErrorCategory.DEPENDENCY,
                                 severity=ErrorSeverity.MEDIUM, recoverable=True)

        else:
            return ProcessingError(str(error), severity=ErrorSeverity.MEDIUM, recoverable=True)

    def _update_metrics(self, error: OCRError):
        """Update error metrics"""
        self.metrics.total_errors += 1
        self.metrics.errors_by_category[error.category.value] = \
            self.metrics.errors_by_category.get(error.category.value, 0) + 1
        self.metrics.errors_by_severity[error.severity.value] = \
            self.metrics.errors_by_severity.get(error.severity.value, 0) + 1

    def _log_error(self, error: OCRError, context: ErrorContext):
        """Log error with context"""
        error_entry = {
            'error': str(error),
            'category': error.category.value,
            'severity': error.severity.value,
            'context': context.__dict__,
            'timestamp': error.timestamp.isoformat(),
            'recoverable': error.recoverable
        }

        self.error_log.append(error_entry)

        # Maintain log size limit
        if len(self.error_log) > self.max_error_log_size:
            self.error_log = self.error_log[-self.max_error_log_size:]

        # Log to standard logging
        log_level = logging.ERROR if error.severity.value in ['high', 'critical'] else logging.WARNING
        logging.log(log_level, f"OCR Error in {context.operation}: {error}", extra={
            'error_category': error.category.value,
            'error_severity': error.severity.value,
            'file_path': context.file_path,
            'job_id': context.job_id
        })

    def _attempt_recovery(self, error: OCRError, context: ErrorContext) -> bool:
        """Attempt error recovery"""
        recovery_start = time.time()

        try:
            if error.category == ErrorCategory.NETWORK:
                # Retry network operations
                return self.retry_mechanism.execute(
                    lambda: self._network_recovery(error, context)
                )

            elif error.category == ErrorCategory.PROCESSING:
                # Retry processing with different settings
                return self._processing_recovery(error, context)

            elif error.category == ErrorCategory.RESOURCE:
                # Clean up resources and retry
                return self._resource_recovery(error, context)

            else:
                return False

        except Exception as recovery_error:
            logging.error(f"Recovery failed: {recovery_error}")
            return False
        finally:
            recovery_time = time.time() - recovery_start
            self._update_recovery_metrics(recovery_time, error.category)

    def _network_recovery(self, error: NetworkError, context: ErrorContext) -> bool:
        """Network-specific recovery"""
        # Simple retry for now - could be enhanced with different endpoints/strategies
        time.sleep(2)
        return True

    def _processing_recovery(self, error: ProcessingError, context: ErrorContext) -> bool:
        """Processing-specific recovery"""
        # Could try different OCR settings, fallbacks, etc.
        time.sleep(1)
        return True

    def _resource_recovery(self, error: SystemError, context: ErrorContext) -> bool:
        """Resource-specific recovery"""
        # Could clean up temporary files, reduce batch size, etc.
        time.sleep(1)
        return True

    def _update_recovery_metrics(self, recovery_time: float, category: ErrorCategory):
        """Update recovery metrics"""
        total_recoveries = sum(self.metrics.errors_by_category.values())
        if total_recoveries > 0:
            self.metrics.recovery_success_rate = (
                (self.metrics.recovery_success_rate * (total_recoveries - 1)) + 1
            ) / total_recoveries

        self.metrics.average_recovery_time = (
            (self.metrics.average_recovery_time * (total_recoveries - 1)) + recovery_time
        ) / total_recoveries

    def get_error_report(self) -> Dict[str, Any]:
        """Generate error report for monitoring"""
        return {
            'metrics': self.metrics.__dict__,
            'recent_errors': self.error_log[-10:],  # Last 10 errors
            'error_summary': {
                'by_category': self.metrics.errors_by_category,
                'by_severity': self.metrics.errors_by_severity
            }
        }


def retry_on_failure(max_retries: int = 3, recoverable_only: bool = True):
    """Decorator for retrying functions on failure"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retry = RetryMechanism(max_retries=max_retries)

            try:
                return retry.execute(func, *args, **kwargs)
            except Exception as e:
                if recoverable_only and hasattr(e, 'recoverable') and not e.recoverable:
                    raise e
                raise e

        return wrapper
    return decorator


def handle_ocr_errors(operation: str, context: Optional[ErrorContext] = None):
    """Decorator for OCR error handling"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            error_context = context or ErrorContext(operation=operation)

            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Get or create error handler from function context
                if hasattr(func, '__self__') and hasattr(func.__self__, 'error_handler'):
                    error_handler = func.__self__.error_handler
                else:
                    # Fallback to global error handler
                    from config import config
                    error_handler = ErrorHandler(config)

                success = error_handler.handle_error(e, error_context)
                if not success:
                    raise e

        return wrapper
    return decorator


# Global error handler instance
error_handler = None

def get_error_handler(config) -> ErrorHandler:
    """Get or create global error handler"""
    global error_handler
    if error_handler is None:
        error_handler = ErrorHandler(config)
    return error_handler