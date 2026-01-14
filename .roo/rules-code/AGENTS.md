# Project Coding Rules (Non-Obvious Only)

- Always use `OCRUtils` from `src/ocr_utils.py` instead of direct ocrmypdf library calls
- Use `FileUtils` from `src/ocr_utils.py` for all file operations (ensures consistent error handling and archiving)
- Always use custom error handler from `src/error_handler.py` with `ErrorContext` for structured error information
- Use `log_manager` from `src/logger.py` for all logging (provides structured logging with event types)
- Use dataclass-based config from `src/config.py` with OCR_ prefixed environment variables
- OCR settings must use `--psm 3` tesseract configuration for page segmentation
- Archive directory paths must preserve relative structure when specified
- Background API jobs require proper integration with `progress_tracker` for status updates
- File validation must use `security_validator` before any OCR processing
- Database operations require session management through `database_manager`