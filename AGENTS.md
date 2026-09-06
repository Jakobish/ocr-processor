# AGENTS.md

Project guidance for AI coding agents working on this Python OCR application.

## Commands

- Install dependencies: `pip install -r requirements.txt`
- Run one test: `python -m unittest tests.test_ocr_utils.TestOCRUtils.test_get_ocr_settings_cli_mode`
- Run the suite: `python -m unittest tests/` or `python -m pytest tests/`
- Run the CLI: `python cli/ocr_combined.py --mode cli document.pdf`
- Run a GUI locally: `python cli/pdf_ocr_gui.py`
- There is no configured Python lint or build command. The VS Code `dotnet build` task is unrelated.

Do not assume the documented Uvicorn or Docker entry points work: `src/api_server.py` exposes `get_api_server(config)`, not a module-level `app`, and the current Docker image does not copy `cli/`. Verify API/container wiring before changing or documenting it.

## Architecture

- `src/ocr_utils.py`: core OCR, file handling, and input collection (`OCRUtils`, `FileUtils`, `InputProcessor`)
- `cli/ocr_combined.py`: command-line entry point
- `cli/pdf_ocr_gui.py`: desktop GUI entry point
- `src/api_server.py`: API server and job endpoints
- `src/config.py`: dataclass configuration, JSON config loading, and `OCR_` environment variables
- `src/progress_tracker.py`, `src/database_manager.py`, `src/notification_manager.py`: job state and integrations
- `src/security_validator.py`: validate input before processing

## Implementation Rules

- Call OCR through `OCRUtils`; do not call `ocrmypdf` directly.
- Use `FileUtils` for output, archiving, and zip operations.
- Use `ErrorContext` and the custom handler in `src/error_handler.py` for structured errors.
- Use `log_manager` from `src/logger.py` for structured logging and include event types.
- Use dataclass configuration from `src/config.py`; environment variables use the `OCR_` prefix.
- Preserve Tesseract `--psm 3` in OCR settings.
- Validate files with `security_validator` before OCR.
- Route API job state through `progress_tracker` and database work through `database_manager`.

## OCR Contract

- Modes are `cli`, `force`, and `visual`.
- `cli`: `force_ocr=False`, `skip_text=True`.
- `force`: `force_ocr=True`, `skip_text=False`.
- `visual`: `force_ocr=False`, `skip_text=True`.
- Default language is `heb+eng`.
- Results use `ocr_<mode>/<filename>_<timestamp>/` with PDF, text, and log output; force mode may also produce a zip.
- When archiving originals, preserve their relative directory structure.

## Documentation

- [Complete technical documentation](docs/COMPLETE_DOCUMENTATION.md)
- [Deployment guidance](docs/DEPLOYMENT.md)
- [Administration and monitoring](docs/ADMIN_GUIDE.md)
- [OCR utility tests](tests/test_ocr_utils.py)

Keep this file focused on agent-discoverable conventions. Use the linked documents for detailed operational guidance. There is no indexed session history for this repository yet; use `/chronicle improve` after future work to refine these instructions from recurring friction.
