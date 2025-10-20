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
import os
import sys
import shutil
import logging
import argparse
import filecmp
import zipfile
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
import fitz  # PyMuPDF
import ocrmypdf
from ocrmypdf.exceptions import InputFileError, PriorOcrFoundError

def ensure_dir(path: Path):
    """Create directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)

def filecompare(a, b):
    """Compare two files for equality."""
    try:
        return filecmp.cmp(a, b, shallow=True)
    except FileNotFoundError:
        return False

def zip_folder(folder_path: Path):
    """Create a zip file from a folder."""
    zip_path = folder_path.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for path in folder_path.rglob("*"):
            if path.is_file():
                zipf.write(path, arcname=path.relative_to(folder_path))
    print(f"📦 Output zipped to: {zip_path.name}")

def visualize_hocr(hocr_path: Path, original_pdf: Path, vis_output_folder: Path):
    """Generate visual highlights from HOCR file."""
    print("🖼️ Generating visual highlight from HOCR...")
    doc = fitz.open(original_pdf)
    soup = BeautifulSoup(hocr_path.read_text(encoding='utf-8'), 'html.parser')

    words = soup.find_all("span", class_="ocrx_word")
    coords_per_page = {}

    for word in words:
        if "title" in word.attrs:
            parts = word["title"].split(";")
            bbox = parts[0].replace("bbox", "").strip()
            coords = list(map(int, bbox.split()))
            page_num = int(word.parent["id"].split("_")[-1])
            coords_per_page.setdefault(page_num, []).append(coords)

    ensure_dir(vis_output_folder)

    for page_num, coords_list in coords_per_page.items():
        if page_num >= len(doc):
            continue

        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(img)

        for box in coords_list:
            # Ensure coordinates are valid
            if len(box) >= 4:
                x1, y1, x2, y2 = box[:4]
                # Draw rectangle with red outline
                draw.rectangle([x1, y1, x2, y2], outline="red", width=2)

        output_path = vis_output_folder / f"page_{page_num + 1:03d}.png"
        img.save(output_path)

    print(f"📸 Highlighted images saved in: {vis_output_folder}")

def get_ocr_settings(mode: str, lang: str = "heb+eng"):
    """Get OCR settings based on mode."""
    base_settings = {
        'deskew': True,
        'output_type': 'pdfa',
        'progress_bar': True,
        'skip_big': False,
        'fast_web_view': True,
        'optimize_images': True,
        'clean': True,
        'lang': lang,
        'clean_final': True,
        'oversample': 300,
        'jobs': 0,  # Use all available CPU cores
        'tesseract_config': '--psm 3',
    }

    if mode == "cli":
        # CLI mode: skip existing text
        base_settings.update({
            'force_ocr': False,
            'skip_text': True,
        })
    elif mode == "force":
        # Force mode: force OCR everything
        base_settings.update({
            'force_ocr': True,
            'skip_text': False,
        })
    elif mode == "visual":
        # Visual mode: skip existing text but create visuals
        base_settings.update({
            'force_ocr': False,
            'skip_text': True,
        })
    else:
        raise ValueError(f"Unknown mode: {mode}")

    return base_settings

def archive_file(source_file: Path, archive_dir: Path):
    """Archive original file before OCR processing."""
    archive_filename = archive_dir / source_file.relative_to(source_file.parent.parent)
    if not filecompare(source_file, archive_filename):
        print(f"📁 Archiving original file to: {archive_filename}")
        try:
            archive_filename.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, archive_filename)
        except OSError:
            archive_filename.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, archive_filename)

def ocr_process(pdf_file: Path, output_base: Path, mode: str, lang: str = "heb+eng", archive_dir: Path = None):
    """Process a PDF file with OCR based on specified mode."""
    ensure_dir(output_base)

    # Archive original file if archive directory is specified
    if archive_dir:
        archive_file(pdf_file, archive_dir)

    # Define output files
    pdf_output = output_base / "ocr_output.pdf"
    sidecar_txt = output_base / "ocr_output.txt"
    hocr_output = output_base / "ocr_output.hocr"
    log_file = output_base / "ocr_log.txt"

    # Get OCR settings for the mode
    ocr_settings = get_ocr_settings(mode, lang)

    # Set up logging for this file
    file_logger = logging.getLogger(f"ocr_process_{pdf_file.stem}")
    file_logger.setLevel(logging.INFO)

    # Remove any existing handlers to avoid duplicates
    for handler in file_logger.handlers[:]:
        file_logger.removeHandler(handler)

    # Add file handler for this specific file
    handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    file_logger.addHandler(handler)

    try:
        print(f"🔄 Processing: {pdf_file.name}")

        # Run OCR using ocrmypdf as a library
        result = ocrmypdf.ocr(
            pdf_file,
            pdf_output,
            sidecar=sidecar_txt,
            hocr=hocr_output,
            **ocr_settings
        )

        print(f"✅ OCR completed for {pdf_file.name}")
        print(f"📄 PDF with OCR: {pdf_output}")
        print(f"📝 Extracted text: {sidecar_txt}")
        print(f"📐 HOCR layout: {hocr_output}")
        print(f"📜 Log file: {log_file}")

        # Generate visual highlights for force and visual modes
        if mode in ["force", "visual"] and hocr_output.exists():
            vis_folder = output_base / "visual"
            visualize_hocr(hocr_output, pdf_file, vis_folder)

        # Create zip file for force mode
        if mode == "force":
            zip_folder(output_base)

        file_logger.info(f"Successfully processed {pdf_file.name}")
        return True

    except PriorOcrFoundError:
        print(f"⚠️ Skipping {pdf_file.name} - already contains OCR text")
        file_logger.info(f"Skipped {pdf_file.name} - already contains OCR text")
        return False
    except InputFileError as e:
        print(f"❌ Input file error for {pdf_file.name}: {e}")
        file_logger.error(f"Input file error for {pdf_file.name}: {e}")
        return False
    except Exception as e:
        print(f"❌ Error processing {pdf_file.name}: {e}")
        file_logger.error(f"Error processing {pdf_file.name}: {e}")
        return False

def process_input(input_path: Path, mode: str, lang: str = "heb+eng", archive_dir: Path = None, recursive: bool = True):
    """Process a single PDF file or all PDFs in a directory."""
    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        pdfs = [input_path]
    elif input_path.is_dir():
        if recursive:
            pdfs = list(input_path.glob("**/*.pdf"))
        else:
            pdfs = list(input_path.glob("*.pdf"))

        if not pdfs:
            print(f"❌ No PDF files found in directory: {input_path}")
            return
    else:
        print("❌ Invalid input. Provide PDF file or folder containing PDFs.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    processed_count = 0
    skipped_count = 0

    for pdf in pdfs:
        print(f"\n🔄 Processing: {pdf.name}")
        base = Path(f"ocr_{mode}") / f"{pdf.stem}_{timestamp}"
        success = ocr_process(pdf, base, mode, lang, archive_dir)
        if success:
            processed_count += 1
        else:
            skipped_count += 1

    print("\n🎉 Processing completed!")
    print(f"📊 Processed: {processed_count} files")
    print(f"⏭️ Skipped: {skipped_count} files")

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