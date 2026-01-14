#!/usr/bin/env python3
#############################################
# Script: ocr_highlight_visual.py
# Purpose:
#   This Python script performs OCR on a PDF and visually highlights recognized text areas.
#   It:
#     - Accepts a PDF file or folder of PDFs as input
#     - Runs OCR using ocrmypdf with deskew, auto-rotate, and HOCR output
#     - Extracts:
#         - OCRed PDF
#         - Sidecar text (.txt) and HOCR layout file (.hocr)
#     - Parses HOCR to find bounding boxes of recognized words
#     - Uses PyMuPDF and PIL to overlay rectangles on original pages
#     - Saves highlighted page images in PNG format
# Output:
#   - Output saved under: ocr_visual/<filename>_<timestamp>/
#   - Includes PDF, HOCR, sidecar text, and PNGs with highlights
#############################################
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
import fitz  # PyMuPDF

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

def ocr_process(pdf_file: Path, output_base: Path, lang="heb+eng"):
    ensure_dir(output_base)

    pdf_output = output_base / "ocr_output.pdf"
    sidecar_txt = output_base / "ocr_output.txt"
    hocr_output = output_base / "ocr_output.hocr"
    log_file = output_base / "ocr_log.txt"
    vis_folder = output_base / "visual"
    ensure_dir(vis_folder)

    cmd = f'''
ocrmypdf --output-type pdf \
         --rotate-pages \
         --deskew \
         --skip-text \
         -l {lang} \
         --sidecar "{sidecar_txt}" \
         --sidecar-hocr "{hocr_output}" \
         "{pdf_file}" "{pdf_output}"
    '''
    log = run_cmd(cmd)
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(log)

    print(f"✅ OCR completed: {pdf_file.name}")
    visualize_hocr(hocr_output, pdf_file, vis_folder)

def visualize_hocr(hocr_path: Path, original_pdf: Path, vis_output_folder: Path):
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

    for page_num, coords_list in coords_per_page.items():
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(img)

        for box in coords_list:
            draw.rectangle(box, outline="red", width=2)

        img.save(vis_output_folder / f"page_{page_num + 1:03d}.png")

    print(f"📸 Highlighted images saved in: {vis_output_folder}")

def main():
    if len(sys.argv) < 2:
        print("Usage: ocr_highlight_visual.py <pdf_file_or_folder>")
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
        base = Path("ocr_visual") / f"{pdf.stem}_{timestamp}"
        ocr_process(pdf, base)

if __name__ == "__main__":
    main()
