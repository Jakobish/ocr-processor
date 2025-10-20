#!/usr/bin/env python3
#############################################
# Script: ocr_highlight_cli.py
# Purpose:
#   This script performs OCR (Optical Character Recognition) on PDF files using ocrmypdf.
#   It:
#     - Accepts a single PDF file or a folder containing multiple PDFs
#     - Runs OCR with deskewing, auto-rotation, and skipping of already recognized text
#     - Produces:
#         - OCR-enhanced PDF
#         - Sidecar plain text output (.txt)
#         - HOCR layout file (.hocr) with spatial layout info
#         - Log file capturing full ocrmypdf command output
# Output:
#   - Results are saved under: ocr_results/<filename>_<timestamp>/
#   - Each run gets a unique timestamped folder
#############################################
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def run_cmd(cmd):
    try:
        print(f"🔧 Running: {cmd}")
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return result.stdout + result.stderr
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e}")
        return e.output + e.stderr

def ocr_process(pdf_file: Path, output_base: Path):
    ensure_dir(output_base)

    pdf_output = output_base / "ocr_output.pdf"
    sidecar_txt = output_base / "ocr_output.txt"
    hocr_output = output_base / "ocr_output.hocr"
    log_file = output_base / "ocr_log.txt"

    cmd = f'''
ocrmypdf --output-type pdf \
         --rotate-pages \
         --deskew \
         --skip-text \
         --sidecar "{sidecar_txt}" \
         --sidecar-hocr "{hocr_output}" \
         "{pdf_file}" "{pdf_output}"
    '''
    log = run_cmd(cmd)
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(log)

    print(f"✅ OCR completed for {pdf_file.name}")
    print(f"📄 PDF with OCR: {pdf_output}")
    print(f"📝 Extracted text: {sidecar_txt}")
    print(f"📐 HOCR layout: {hocr_output}")
    print(f"📜 Log file: {log_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage: ocr_highlight_cli.py <pdf_file_or_folder>")
        return

    input_path = Path(sys.argv[1])

    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        pdfs = [input_path]
    elif input_path.is_dir():
        pdfs = list(input_path.glob("*.pdf"))
    else:
        print("❌ Invalid input. Provide PDF file or folder.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for pdf in pdfs:
        base = Path("ocr_results") / f"{pdf.stem}_{timestamp}"
        ocr_process(pdf, base)

if __name__ == "__main__":
    main()
