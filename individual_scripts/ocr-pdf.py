#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2016 findingorder <https://github.com/findingorder>
# SPDX-FileCopyrightText: 2024 nilsro <https://github.com/nilsro>
# SPDX-License-Identifier: MIT

"""Example of using ocrmypdf as a library in a script.

This script will recursively search a directory for PDF files and run OCR on
them. It will log the results. It runs OCR on every file, even if it already
has text. OCRmyPDF will detect files that already have text.

You should edit this script to meet your needs.
"""

from __future__ import annotations

import filecmp
import logging
import os
import shutil
import sys
from pathlib import Path

import ocrmypdf
import logging
import argparse
from ocrmypdf.exceptions import InputFileError


# pylint: disable=logging-format-interpolation
# pylint: disable=logging-not-lazy


def filecompare(a, b):
    try:
        return filecmp.cmp(a, b, shallow=True)
    except FileNotFoundError:
        return False


script_dir = Path(__file__).parent

parser = argparse.ArgumentParser(
    description="Recursively OCR PDFs in a directory."
)
parser.add_argument(
    "start_dir",
    nargs="?",
    type=Path,
    default=Path("."),
    help="Directory to start searching for PDFs (default: current directory)",
)
parser.add_argument(
    "--log-file",
    type=Path,
    default=script_dir.with_name("ocr-tree.log"),
    help="Path to the log file (default: ocr-tree.log in script directory)",
)
parser.add_argument(
    "--archive-dir",
    type=Path,
    default="../../archive",  
    help="Path for backup original documents. If not provided, no archiving will be done.",
)

args = parser.parse_args()

start_dir = args.start_dir
log_file = args.log_file
archive_dir = args.archive_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    filename=log_file,
    filemode="a",
)

logging.info(f"Start directory {start_dir}")

ocrmypdf.configure_logging(ocrmypdf.Verbosity.default)

for filename in start_dir.glob("**/*.pdf"):
    logging.info(f"Processing {filename}")
    if ocrmypdf.pdfa.file_claims_pdfa(filename)["pass"]:
        logging.info("Skipped document because it already contained text")
    else:
        archive_filename = archive_dir / filename.relative_to(start_dir)
        if archive_dir and not filecompare(filename, archive_filename):
            logging.info(f"Archiving document to {archive_filename}")
            try:
                shutil.copy2(filename, archive_filename.parent)
            except OSError:
                os.makedirs(archive_filename.parent, exist_ok=True)
                shutil.copy2(filename, archive_filename.parent)
        try:
            # Define OCR settings in a dictionary for easier management
            ocr_settings = {
                'deskew': True,
                'force_ocr': False,  # OCRmyPDF will detect files that already have text
                'output_type': 'pdfa',
                'progress_bar': True,
                'skip_big': False,
                'skip_text': True,
                'fast_web_view': True,
                'optimize_images': True,
                'clean': True,
                'lang': 'heb+eng',
                'clean_final': True,
                'oversample': 300,
                'jobs': 0, # Use all available CPU cores
                'tesseract_config': '--psm 3', # Page segmentation mode for Tesseract
                'language': 'eng+heb', # English and Hebrew languages
            }

            result = ocrmypdf.ocr(filename, filename, **ocr_settings)
            logging.info(result)
        except InputFileError as e:
            logging.error(f"Input file error for {filename}: {e}")
        except ChildProcessError as e:
            logging.error(f"OCRmyPDF child process error for {filename}: {e}")
        except Exception as e:
            logging.error(f"Unhandled error occurred for {filename}: {e}")
            logging.error(e.__traceback__)
        logging.info("OCR complete")
