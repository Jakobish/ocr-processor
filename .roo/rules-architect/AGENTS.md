# Project Architecture Rules (Non-Obvious Only)

- OCR processing is abstracted through `OCRUtils` class (not direct ocrmypdf usage)
- Configuration uses dataclass with automatic env var loading and JSON file support
- Error handling requires `ErrorContext` objects for structured error information
- Logging is centralized through `log_manager` with event type classification
- File operations must use `FileUtils` for consistent behavior and error handling
- API server uses FastAPI with custom middleware for request/response logging
- Background job processing requires integration with `progress_tracker` for status management
- Security validation is mandatory before any file processing operations
- Database operations are abstracted through `database_manager` with session management
- Notification system supports multiple channels (email, webhook, Slack) through unified interface