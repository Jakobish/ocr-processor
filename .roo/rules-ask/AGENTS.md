# Project Documentation Rules (Non-Obvious Only)

- OCR processing outputs are stored in timestamped directories: `ocr_<mode>/<filename>_<timestamp>/`
- CLI tool accepts both single files and directories (recursive by default)
- API endpoints include job management, batch processing, and file upload capabilities
- Configuration supports both JSON files and environment variables with OCR_ prefix
- Three OCR modes have specific behaviors: cli (fast), force (thorough with zip), visual (layout analysis)
- Archive functionality preserves relative directory structure when enabled
- Language support defaults to `heb+eng` for mixed Hebrew/English documents
- Progress tracking provides real-time updates for long-running OCR jobs
- Security validation occurs before any file processing operations
- Database integration is optional but provides persistent job tracking when enabled