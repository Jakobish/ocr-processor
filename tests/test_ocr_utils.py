"""
Unit tests for OCR utilities library
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
import sys
from ocrmypdf.exceptions import PriorOcrFoundError

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ocr_utils import FileUtils, OCRUtils, InputProcessor


class TestFileUtils(unittest.TestCase):
    """Test FileUtils class"""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_ensure_dir_creates_directory(self):
        """Test ensure_dir creates directory when it doesn't exist"""
        test_path = self.temp_dir / "test_dir" / "nested"
        result = FileUtils.ensure_dir(test_path)

        self.assertTrue(test_path.exists())
        self.assertTrue(test_path.is_dir())
        self.assertEqual(result, test_path)

    def test_ensure_dir_existing_directory(self):
        """Test ensure_dir works with existing directory"""
        test_path = self.temp_dir / "existing_dir"
        test_path.mkdir()

        result = FileUtils.ensure_dir(test_path)

        self.assertTrue(test_path.exists())
        self.assertEqual(result, test_path)

    def test_filecompare_identical_files(self):
        """Test filecompare returns True for identical files"""
        file1 = self.temp_dir / "file1.txt"
        file2 = self.temp_dir / "file2.txt"

        content = "test content"
        file1.write_text(content)
        file2.write_text(content)

        result = FileUtils.filecompare(file1, file2)
        self.assertTrue(result)

    def test_filecompare_different_files(self):
        """Test filecompare returns False for different files"""
        file1 = self.temp_dir / "file1.txt"
        file2 = self.temp_dir / "file2.txt"

        file1.write_text("content 1")
        file2.write_text("content 2")

        result = FileUtils.filecompare(file1, file2)
        self.assertFalse(result)

    def test_filecompare_missing_file(self):
        """Test filecompare handles missing files gracefully"""
        file1 = self.temp_dir / "file1.txt"
        file2 = self.temp_dir / "file2.txt"

        file1.write_text("content")

        result = FileUtils.filecompare(file1, file2)
        self.assertFalse(result)

    def test_zip_folder_creates_zip(self):
        """Test zip_folder creates zip file"""
        # Create test directory with files
        test_dir = self.temp_dir / "test_files"
        test_dir.mkdir()

        (test_dir / "file1.txt").write_text("content 1")
        (test_dir / "file2.txt").write_text("content 2")

        # Create zip
        zip_path = FileUtils.zip_folder(test_dir)

        # Verify zip was created
        self.assertTrue(zip_path.exists())
        self.assertTrue(zip_path.suffix == ".zip")

        # Verify zip contents
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            files = zipf.namelist()
            self.assertIn("file1.txt", files)
            self.assertIn("file2.txt", files)


class TestOCRUtils(unittest.TestCase):
    """Test OCRUtils class"""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_get_ocr_settings_cli_mode(self):
        """Test get_ocr_settings for CLI mode"""
        settings = OCRUtils.get_ocr_settings("cli", "heb+eng")

        self.assertIn('force_ocr', settings)
        self.assertIn('skip_text', settings)
        self.assertFalse(settings['force_ocr'])
        self.assertTrue(settings['skip_text'])
        self.assertEqual(settings['lang'], "heb+eng")

    def test_get_ocr_settings_force_mode(self):
        """Test get_ocr_settings for force mode"""
        settings = OCRUtils.get_ocr_settings("force", "eng")

        self.assertTrue(settings['force_ocr'])
        self.assertFalse(settings['skip_text'])
        self.assertEqual(settings['lang'], "eng")

    def test_get_ocr_settings_visual_mode(self):
        """Test get_ocr_settings for visual mode"""
        settings = OCRUtils.get_ocr_settings("visual", "heb+eng")

        self.assertFalse(settings['force_ocr'])
        self.assertTrue(settings['skip_text'])

    def test_get_ocr_settings_invalid_mode(self):
        """Test get_ocr_settings raises error for invalid mode"""
        with self.assertRaises(ValueError):
            OCRUtils.get_ocr_settings("invalid_mode")

    @patch('ocr_utils.ocrmypdf.ocr')
    def test_ocr_process_success(self, mock_ocr):
        """Test successful OCR processing"""
        pdf_file = Path(__file__).parent / "PDF" / "LaTeX Guide.pdf"

        output_base = self.temp_dir / "output"
        mock_ocr.return_value = None

        result = OCRUtils.ocr_process(pdf_file, output_base, "cli", "heb+eng")

        self.assertTrue(result)
        self.assertTrue(output_base.exists())
        mock_ocr.assert_called_once()

    @patch('ocr_utils.ocrmypdf.ocr')
    def test_ocr_process_prior_ocr_found(self, mock_ocr):
        """Test OCR processing when OCR already exists"""
        mock_ocr.side_effect = PriorOcrFoundError()

        pdf_file = Path(__file__).parent / "PDF" / "LaTeX Guide.pdf"

        output_base = self.temp_dir / "output"

        result = OCRUtils.ocr_process(pdf_file, output_base, "cli", "heb+eng")

        self.assertFalse(result)  # Should return False for skipped files


class TestInputProcessor(unittest.TestCase):
    """Test InputProcessor class"""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_validate_input_path_valid_pdf(self):
        """Test validate_input_path with valid PDF file"""
        pdf_file = Path(__file__).parent / "PDF" / "LaTeX Guide.pdf"

        result = InputProcessor.validate_input_path(pdf_file)
        self.assertTrue(result)

    def test_validate_input_path_valid_directory(self):
        """Test validate_input_path with directory containing PDFs"""
        pdf_dir = Path(__file__).parent / "PDF"

        result = InputProcessor.validate_input_path(pdf_dir)
        self.assertTrue(result)

    def test_validate_input_path_empty_directory(self):
        """Test validate_input_path with empty directory"""
        result = InputProcessor.validate_input_path(self.temp_dir)
        self.assertFalse(result)

    def test_validate_input_path_invalid_file(self):
        """Test validate_input_path with non-PDF file"""
        txt_file = self.temp_dir / "test.txt"
        txt_file.write_text("text content")

        result = InputProcessor.validate_input_path(txt_file)
        self.assertFalse(result)

    def test_collect_pdf_files_single_file(self):
        """Test collect_pdf_files with single PDF file"""
        pdf_file = Path(__file__).parent / "PDF" / "LaTeX Guide.pdf"

        files = InputProcessor.collect_pdf_files(pdf_file)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], pdf_file)

    def test_collect_pdf_files_directory(self):
        """Test collect_pdf_files with directory"""
        pdf_dir = Path(__file__).parent / "PDF"

        files = InputProcessor.collect_pdf_files(pdf_dir)
        self.assertEqual(len(files), 2)
        self.assertIn(pdf_dir / "LaTeX Guide.pdf", files)
        self.assertIn(pdf_dir / "r2_cs.pdf", files)

    def test_collect_pdf_files_recursive(self):
        """Test collect_pdf_files with recursive search"""
        sub_dir = self.temp_dir / "subdir"
        sub_dir.mkdir()

        pdf1 = self.temp_dir / "test1.pdf"
        pdf2 = sub_dir / "test2.pdf"

        pdf1.write_text("pdf1")
        pdf2.write_text("pdf2")

        files = InputProcessor.collect_pdf_files(self.temp_dir, recursive=True)
        self.assertEqual(len(files), 2)
        self.assertIn(pdf1, files)
        self.assertIn(pdf2, files)

    def test_collect_pdf_files_non_recursive(self):
        """Test collect_pdf_files without recursive search"""
        sub_dir = self.temp_dir / "subdir"
        sub_dir.mkdir()

        pdf1 = self.temp_dir / "test1.pdf"
        pdf2 = sub_dir / "test2.pdf"

        pdf1.write_text("pdf1")
        pdf2.write_text("pdf2")

        files = InputProcessor.collect_pdf_files(self.temp_dir, recursive=False)
        self.assertEqual(len(files), 1)
        self.assertIn(pdf1, files)
        self.assertNotIn(pdf2, files)


if __name__ == '__main__':
    unittest.main()