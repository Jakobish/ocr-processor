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
import os
import sys
import subprocess
import zipfile
import argparse
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
import fitz  # PyMuPDF

def ensure_dir(path: Path):
    """Create directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)

def run_cmd(cmd):
    """Execute a shell command and return combined output."""
    try:
        print(f"🔧 Running: {cmd}")
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return result.stdout + result.stderr
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e}")
        return e.output + e.stderr

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

def ocr_process(pdf_file: Path, output_base: Path, mode: str, lang: str = "heb+eng"):
    """Process a PDF file with OCR based on specified mode."""
    ensure_dir(output_base)

    # Define output files
    pdf_output = output_base / "ocr_output.pdf"
    sidecar_txt = output_base / "ocr_output.txt"
    hocr_output = output_base / "ocr_output.hocr"
    log_file = output_base / "ocr_log.txt"

    # Build ocrmypdf command based on mode
    base_cmd = "ocrmypdf --output-type pdf --rotate-pages --deskew"

    if mode == "cli":
        # CLI mode: skip existing text
        cmd = f'{base_cmd} --skip-text -l {lang} --sidecar "{sidecar_txt}" --sidecar-hocr "{hocr_output}" "{pdf_file}" "{pdf_output}"'
    elif mode == "force":
        # Force mode: force OCR everything
        cmd = f'{base_cmd} --force-ocr -l {lang} --sidecar "{sidecar_txt}" --sidecar-hocr "{hocr_output}" "{pdf_file}" "{pdf_output}"'
    elif mode == "visual":
        # Visual mode: skip existing text but create visuals
        cmd = f'{base_cmd} --skip-text -l {lang} --sidecar "{sidecar_txt}" --sidecar-hocr "{hocr_output}" "{pdf_file}" "{pdf_output}"'
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Execute OCR command
    log = run_cmd(cmd)
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(log)

    print(f"✅ OCR completed for {pdf_file.name}")
    print(f"📄 PDF with OCR: {pdf_output}")
    print(f"📝 Extracted text: {sidecar_txt}")
    print(f"📐 HOCR layout: {hocr_output}")
    print(f"📜 Log file: {log_file}")

    # Generate visual highlights for force and visual modes
    if mode in ["force", "visual"]:
        vis_folder = output_base / "visual"
        visualize_hocr(hocr_output, pdf_file, vis_folder)

    # Create zip file for force mode
    if mode == "force":
        zip_folder(output_base)

def process_input(input_path: Path, mode: str, lang: str = "heb+eng"):
    """Process a single PDF file or all PDFs in a directory."""
    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        pdfs = [input_path]
    elif input_path.is_dir():
        pdfs = list(input_path.glob("*.pdf"))
        if not pdfs:
            print(f"❌ No PDF files found in directory: {input_path}")
            return
    else:
        print("❌ Invalid input. Provide PDF file or folder containing PDFs.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for pdf in pdfs:
        print(f"\n🔄 Processing: {pdf.name}")
        base = Path(f"ocr_{mode}") / f"{pdf.stem}_{timestamp}"
        ocr_process(pdf, base, mode, lang)

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