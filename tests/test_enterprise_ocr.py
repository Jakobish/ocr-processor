"""Contract tests use real PDFs and replace only the external OCR operation."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import fitz
try:
    import security_validator
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
from enterprise.ocr_runner import run


@unittest.skipUnless(SECURITY_AVAILABLE, "Native libmagic is required")
class RunnerTests(unittest.TestCase):
    def test_extracts_text_from_all_final_pdf_pages(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source.pdf'
            output = Path(temp) / 'attempt'
            with fitz.open() as document:
                document.new_page().insert_text((50, 50), 'Already searchable page')
                document.new_page().insert_text((50, 50), 'Newly OCRed page')
                document.save(source)
            def ocr(src, out, mode, lang, **kwargs):
                (out / 'ocr_output.pdf').write_bytes(src.read_bytes())
                (out / 'ocr_output.txt').write_text('Newly OCRed page')
                return True
            with patch('ocr_utils.OCRUtils.ocr_process', side_effect=ocr), patch('security_validator.get_security_validator') as validator:
                validator.return_value.validate_pdf_file.return_value.is_valid = True
                self.assertEqual(run(source, output, 'force', 'eng'), 0)
            text = (output / 'ocr_output.txt').read_text()
            self.assertIn('Already searchable page', text)
            self.assertIn('Newly OCRed page', text)
            import zipfile
            with zipfile.ZipFile(output.with_suffix('.zip')) as archive:
                self.assertEqual(archive.read('ocr_output.txt').decode(), text)

    def test_rejected_file_never_reaches_ocr(self):
        with patch('ocr_utils.OCRUtils.ocr_process') as ocr, patch('security_validator.get_security_validator') as validator:
            validator.return_value.validate_pdf_file.return_value.is_valid = False
            self.assertEqual(run(Path('rejected.pdf'), Path('unused'), 'cli', 'eng'), 2)
            ocr.assert_not_called()

class NativeBoundaryTests(unittest.TestCase):
    def test_translates_cli_settings_to_library_arguments(self):
        from ocr_utils import OCRUtils
        with tempfile.TemporaryDirectory() as temp, patch('ocr_utils.ocrmypdf.ocr') as ocr:
            self.assertTrue(OCRUtils.ocr_process(Path('source.pdf'), Path(temp), 'cli', 'eng', raise_errors=True))
            options = ocr.call_args.kwargs
            self.assertEqual(options['language'], 'eng')
            self.assertEqual(options['tesseract_pagesegmode'], 3)
            self.assertNotIn('lang', options)
            self.assertNotIn('tesseract_config', options)

    def test_runtime_exception_propagates_for_durable_retry(self):
        from ocr_utils import OCRUtils
        with tempfile.TemporaryDirectory() as temp, patch('ocr_utils.ocrmypdf.ocr', side_effect=OSError('temporary')):
            with self.assertRaises(OSError):
                OCRUtils.ocr_process(Path('source.pdf'), Path(temp), 'cli', raise_errors=True)

    def test_security_accepts_real_pdf_and_rejects_fake_and_javascript(self):
        from security_validator import SecurityValidator
        from config import config
        validator = SecurityValidator(config)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source.pdf'
            with fitz.open() as document:
                document.new_page().insert_text((50, 50), 'Ordinary PDF stream')
                document.save(source)
            self.assertTrue(validator.validate_pdf_file(source).is_valid)
            source.write_bytes(b'%PDF-1.4\nnot a real PDF')
            self.assertFalse(validator.validate_pdf_file(source).is_valid)
            with fitz.open() as document:
                document.new_page()
                xref = document.get_new_xref()
                document.update_object(xref, '<< /S /JavaScript /JS (app.alert\\(1\\)) >>')
                document.xref_set_key(document.pdf_catalog(), 'OpenAction', f'{xref} 0 R')
                document.save(source)
            self.assertFalse(validator.validate_pdf_file(source).is_valid)
