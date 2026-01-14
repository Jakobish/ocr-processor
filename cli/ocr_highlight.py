#!/usr/bin/env python3
#############################################
# Script: ocr_highlight_combined.py
# Purpose:
#   This script combines the functionality of three OCR scripts into one unified tool:
#   - CLI mode: Basic OCR with --skip-text (equivalent to ocr_highlight_cli.py)
#   - Force mode: Forced OCR with --force-ocr + visual highlights + zip (equivalent to ocr_highlight_force.py)
#   - Visual mode: OCR with --skip-text + visual highlights (equivalent to ocr_highlight_visual.py)
#
# Features:
#   - Accepts a single PDF file or a folder containing multiple PDFs
#   - Multiple OCR modes: cli, force, visual
#   - Configurable language support (default: heb+eng)
#   - Produces various outputs based on mode:
#       - OCR-enhanced PDF
#       - Sidecar plain text output (.txt)
#       - HOCR layout file (.hocr) with spatial layout info
#       - Visual overlay with highlighted bounding boxes (force/visual modes)
#       - Log file capturing full ocrmypdf command output
#       - Zipped output (force mode only)
# Output:
#   - Results are saved under: ocr_<mode>/<filename>_<timestamp>/
#   - Each run gets a unique timestamped folder
#############################################
import sys
import argparse
from pathlib import Path

# Import centralized utilities
sys.path.append(str(Path(__file__).parent.parent / "src"))
from ocr_utils import OCRUtils, InputProcessor

def ocr_process(pdf_file: Path, output_base: Path, mode: str, lang: str = "heb+eng"):
    """Process a PDF file with OCR based on specified mode."""
    # Use the centralized OCR processing
    return OCRUtils.ocr_process(pdf_file, output_base, mode, lang)

def process_input(input_path: Path, mode: str, lang: str = "heb+eng"):
    """Process a single PDF file or all PDFs in a directory."""
    return InputProcessor.process_input(input_path, mode, lang)

def main():
    parser = argparse.ArgumentParser(
        description="Unified OCR tool with multiple processing modes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  cli     - Basic OCR with --skip-text (fastest, preserves existing text)
  force   - Forced OCR with --force-ocr + visual highlights + zip output
  visual  - OCR with --skip-text + visual highlights (no zip)

Examples:
  python ocr_highlight_combined.py --mode cli document.pdf
  python ocr_highlight_combined.py --mode force documents/
  python ocr_highlight_combined.py --mode visual --lang eng document.pdf
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

    args = parser.parse_args()

    # Handle backward compatibility - if no --mode specified, check script name
    if len(sys.argv) == 2:
        script_name = sys.argv[0]
        if "cli" in script_name:
            args.mode = "cli"
        elif "force" in script_name:
            args.mode = "force"
        elif "visual" in script_name:
            args.mode = "visual"

    print(f"🚀 Starting OCR processing in {args.mode} mode...")
    process_input(Path(args.input_path), args.mode, args.lang)
    print("🎉 All processing completed!")

if __name__ == "__main__":
    main()