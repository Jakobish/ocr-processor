# Project Debug Rules (Non-Obvious Only)

- OCR processing logs are written to individual `ocr_log.txt` files in each output directory
- API request/response logging is handled by middleware in `api_server.py` (not standard FastAPI logging)
- Job progress tracking requires `progress_tracker` integration for real-time status updates
- File validation errors are logged through `security_validator` with detailed issue descriptions
- Database connection issues are logged with specific error context in `database_manager`
- Notification failures are logged through `notification_manager` with delivery status
- OCR processing failures include detailed ocrmypdf error information in log files
- Background job processing errors are captured in `progress_tracker` with full stack traces
- File archiving operations log both source and destination paths for troubleshooting
- API health checks validate database connectivity and storage write permissions