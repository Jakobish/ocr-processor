# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Build/Lint/Test Commands

- **Run single test**: `python -m unittest tests.test_ocr_utils.TestOCRUtils.test_get_ocr_settings_cli_mode`
- **Run all tests**: `python -m unittest tests/` or `python -m pytest tests/`
- **Run CLI tool**: `python cli/ocr_combined.py --mode cli document.pdf`
- **Start API server**: `python -m uvicorn src.api_server:app --host 0.0.0.0 --port 8000`

## Code Style Guidelines

- **Error handling**: Always use custom error handler from `src/error_handler.py` with `ErrorContext` for structured error information
- **Logging**: Use `log_manager` from `src/logger.py` for all logging, includes structured logging with event types
- **Configuration**: Use dataclass-based config from `src/config.py` with environment variable loading (OCR_ prefix)
- **OCR utilities**: Always use `OCRUtils` from `src/ocr_utils.py` instead of direct ocrmypdf calls
- **File operations**: Use `FileUtils` from `src/ocr_utils.py` for consistent file handling and archiving
- **Tesseract config**: Use `--psm 3` for page segmentation mode in OCR settings

## Project-Specific Patterns

- **OCR modes**: Three modes with specific ocrmypdf settings:
  - `cli`: `force_ocr=False, skip_text=True` (fast, preserves existing text)
  - `force`: `force_ocr=True, skip_text=False` (thorough, replaces all text)
  - `visual`: `force_ocr=False, skip_text=True` (preserves text, adds visual overlays)
- **Output structure**: Results saved to `ocr_<mode>/<filename>_<timestamp>/` with PDF, text, log, and optional zip files
- **Archive originals**: When `--archive-dir` specified, creates relative path structure in archive directory
- **Language default**: `heb+eng` for Hebrew+English mixed documents
- **API integration**: Jobs run as background tasks with progress tracking via `progress_tracker`