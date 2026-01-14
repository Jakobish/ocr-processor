#!/usr/bin/env python3
#############################################
# Script: ocr_combined.py
# Purpose:
#   This script combines the functionality of ocr_highlight.py and ocr-pdf.py into one unified tool:
#   - Multiple OCR modes: cli, force, visual (from ocr_highlight.py)
#   - Recursive directory processing (from ocr-pdf.py)
#   - Archiving of original files (from ocr-pdf.py)
#   - Library-based ocrmypdf usage with better error handling (from ocr-pdf.py)
#   - Visual highlighting and HOCR processing (from ocr_highlight.py)
#   - Comprehensive OCR settings and optimization (from ocr-pdf.py)
#
# Features:
#   - Accepts a single PDF file or recursively searches directories for PDFs
#   - Multiple OCR modes: cli, force, visual
#   - Configurable language support (default: heb+eng)
#   - Optional archiving of original files
#   - Produces various outputs based on mode:
#       - OCR-enhanced PDF (PDF/A format)
#       - Sidecar plain text output (.txt)
#       - HOCR layout file (.hocr) with spatial layout info
#       - Visual overlay with highlighted bounding boxes (force/visual modes)
#       - Log file capturing full OCR process
#       - Zipped output (force mode only)
#   - Comprehensive error handling and logging
#   - Progress bar support
#
# Output:
#   - Results are saved under: ocr_<mode>/<filename>_<timestamp>/
#   - Each run gets a unique timestamped folder
#############################################
import sys
import logging
import argparse
from pathlib import Path
from typing import Optional
import ocrmypdf

# Import centralized utilities
sys.path.append(str(Path(__file__).parent.parent / "src"))
from ocr_utils import OCRUtils, InputProcessor

def ocr_process(pdf_file: Path, output_base: Path, mode: str, lang: str = "heb+eng", archive_dir: Optional[Path] = None):
    """Process a PDF file with OCR based on specified mode."""
    return OCRUtils.ocr_process(pdf_file, output_base, mode, lang, archive_dir)

def process_input(input_path: Path, mode: str, lang: str = "heb+eng", archive_dir: Optional[Path] = None, recursive: bool = True):
    """Process a single PDF file or all PDFs in a directory."""
    return InputProcessor.process_input(input_path, mode, lang, archive_dir, recursive)

def main():
    parser = argparse.ArgumentParser(
        description="Unified OCR tool with multiple processing modes and advanced features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  cli     - Basic OCR with --skip-text (fastest, preserves existing text)
  force   - Forced OCR with --force-ocr + visual highlights + zip output
  visual  - OCR with --skip-text + visual highlights (no zip)

Examples:
  python ocr_combined.py --mode cli document.pdf
  python ocr_combined.py --mode force --recursive documents/
  python ocr_combined.py --mode visual --lang eng --archive-dir ./backup document.pdf
  python ocr_combined.py --mode force --no-recursive documents/
        """
    )

    parser.add_argument(
        "input_path",
        help="PDF file or directory containing PDF files to process"
    )

    parser.add_argument(
        "--mode",
        choices=["cli", "force", "visual"],
        default="cli",
        help="OCR processing mode (default: cli)"
    )

    parser.add_argument(
        "--lang",
        default="heb+eng",
        help="Language(s) for OCR (default: heb+eng)"
    )

    parser.add_argument(
        "--archive-dir",
        type=Path,
        help="Directory to archive original files before processing"
    )

    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Disable recursive directory searching (only search top level)"
    )

    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("ocr_combined.log"),
        help="Path to the main log file (default: ocr_combined.log)"
    )

    args = parser.parse_args()

    # Set up main logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(args.log_file, mode='a', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Configure ocrmypdf logging
    ocrmypdf.configure_logging(ocrmypdf.Verbosity.default)

    print(f"🚀 Starting OCR processing in {args.mode} mode...")
    process_input(
        Path(args.input_path),
        args.mode,
        args.lang,
        args.archive_dir,
        recursive=not args.no_recursive
    )

if __name__ == "__main__":
    main()