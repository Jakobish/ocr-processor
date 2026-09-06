"""One OCR attempt; exit 2 denotes an invalid/unprocessable document."""
import argparse
import os
from pathlib import Path


def run(source: Path, output: Path, mode: str, language: str) -> int:
    from config import config
    from error_handler import ErrorContext, get_error_handler, ValidationError
    from logger import log_manager
    from ocr_utils import OCRUtils, FileUtils
    from security_validator import get_security_validator
    import fitz

    try:
        validation = get_security_validator(config).validate_pdf_file(source)
        if not validation.is_valid:
            raise ValidationError('Document failed input validation')
        with fitz.open(source) as document:
            if document.needs_pass or not document.page_count:
                raise ValidationError('Document is encrypted or has no pages')
        FileUtils.ensure_dir(output)
        if not OCRUtils.ocr_process(source, output, mode, language, raise_errors=True):
            return 2
        # Sidecars omit skipped pages. Extract the complete final PDF instead.
        with fitz.open(output / 'ocr_output.pdf') as document:
            if not document.page_count or document.needs_pass:
                raise ValidationError('OCR output is invalid')
            with (output / 'ocr_output.txt').open('w', encoding='utf-8') as text:
                for page in document:
                    text.write(page.get_text())
                    text.write('\n')
        (output / 'ocr_log.txt').write_text('OCR completed successfully.\n', encoding='utf-8')
        if mode == 'force':
            FileUtils.zip_folder(output)
        # Commit file contents and directory entries before DB publication.
        files = list(output.iterdir())
        if mode == 'force':
            files.append(output.with_suffix('.zip'))
        for file in files:
            if file.is_file():
                with file.open('rb') as stream:
                    os.fsync(stream.fileno())
        for directory in (output, output.parent):
            fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        log_manager.logger.info('OCR attempt completed', event_type='durable_ocr_complete')
        return 0
    except ValidationError:
        get_error_handler(config).handle_error(ValidationError('Document validation failed'), ErrorContext(operation='durable_ocr_validation'))
        return 2
    except Exception:
        # Keep paths, native exception text, and document contents out of logs.
        get_error_handler(config).handle_error(RuntimeError('OCR attempt failed'), ErrorContext(operation='durable_ocr'))
        return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--mode', required=True, choices=['cli', 'force', 'visual'])
    parser.add_argument('--language', default='heb+eng')
    args = parser.parse_args()
    raise SystemExit(run(args.source, args.output, args.mode, args.language))


if __name__ == '__main__':
    main()
