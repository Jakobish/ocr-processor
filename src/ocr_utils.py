"""
Enterprise OCR Utilities Library
Provides centralized, reusable utilities for OCR processing operations
"""

import os
import shutil
import logging
import subprocess
import filecmp
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
import fitz  # PyMuPDF
import ocrmypdf
from ocrmypdf.exceptions import InputFileError, PriorOcrFoundError

from logger import log_manager
from error_handler import get_error_handler, ErrorContext, ValidationError
from config import config


class FileUtils:
    """File system utilities for OCR operations"""

    @staticmethod
    def ensure_dir(path: Path) -> Path:
        """Create directory if it doesn't exist.

        Args:
            path: Directory path to create

        Returns:
            Path: The created/ensured directory path
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except Exception as e:
            error_handler = get_error_handler(config)
            error_handler.handle_error(
                e, ErrorContext(operation="ensure_dir", file_path=str(path))
            )
            raise

    @staticmethod
    def filecompare(a: Union[str, Path], b: Union[str, Path]) -> bool:
        """Compare two files for equality.

        Args:
            a: First file path
            b: Second file path

        Returns:
            bool: True if files are identical, False otherwise
        """
        try:
            return filecmp.cmp(str(a), str(b), shallow=True)
        except FileNotFoundError:
            return False
        except Exception as e:
            error_handler = get_error_handler(config)
            error_handler.handle_error(
                e,
                ErrorContext(
                    operation="filecompare",
                    metadata={"file_a": str(a), "file_b": str(b)},
                ),
            )
            return False

    @staticmethod
    def zip_folder(folder_path: Path) -> Path:
        """Create a zip file from a folder.

        Args:
            folder_path: Folder to zip

        Returns:
            Path: Path to the created zip file
        """
        try:
            zip_path = folder_path.with_suffix(".zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for path in folder_path.rglob("*"):
                    if path.is_file():
                        zipf.write(path, arcname=path.relative_to(folder_path))

            print(f"📦 Output zipped to: {zip_path.name}")

            if log_manager and log_manager.logger:
                log_manager.logger.info(
                    "Folder zipped successfully",
                    folder_path=str(folder_path),
                    zip_path=str(zip_path),
                    event_type="folder_zipped",
                )

            return zip_path

        except Exception as e:
            error_handler = get_error_handler(config)
            error_handler.handle_error(
                e, ErrorContext(operation="zip_folder", file_path=str(folder_path))
            )
            raise

    @staticmethod
    def archive_file(source_file: Path, archive_dir: Path) -> Path:
        """Archive original file before OCR processing.

        Args:
            source_file: Source file to archive
            archive_dir: Archive directory

        Returns:
            Path: Path to archived file
        """
        try:
            # Create relative path structure in archive
            archive_filename = archive_dir / source_file.relative_to(
                source_file.parent.parent
            )
            archive_filename.parent.mkdir(parents=True, exist_ok=True)

            if not FileUtils.filecompare(source_file, archive_filename):
                print(f"📁 Archiving original file to: {archive_filename}")
                shutil.copy2(source_file, archive_filename)

                if log_manager and log_manager.logger:
                    log_manager.logger.info(
                        "File archived",
                        source_file=str(source_file),
                        archive_file=str(archive_filename),
                        event_type="file_archived",
                    )

            return archive_filename

        except Exception as e:
            error_handler = get_error_handler(config)
            error_handler.handle_error(
                e,
                ErrorContext(
                    operation="archive_file",
                    file_path=str(source_file),
                    metadata={"archive_dir": str(archive_dir)},
                ),
            )
            raise


class CommandUtils:
    """Command execution utilities"""

    @staticmethod
    def run_cmd(cmd: str) -> str:
        """Execute a shell command and return combined output.

        Args:
            cmd: Command to execute

        Returns:
            str: Combined stdout and stderr output

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        try:
            print(f"🔧 Running: {cmd}")
            result = subprocess.run(
                cmd, shell=True, check=True, capture_output=True, text=True
            )
            return result.stdout + result.stderr

        except subprocess.CalledProcessError as e:
            print(f"❌ Command failed: {e}")
            if log_manager and log_manager.logger:
                log_manager.logger.error(
                    "Command execution failed",
                    command=cmd,
                    return_code=e.returncode,
                    stderr=e.stderr,
                    event_type="command_failed",
                )
            raise


class OCRUtils:
    """OCR-specific utilities"""

    @staticmethod
    def get_ocr_settings(mode: str, lang: str = "heb+eng") -> Dict[str, Any]:
        """Get OCR settings based on mode.

        Args:
            mode: OCR processing mode ('cli', 'force', 'visual')
            lang: Language for OCR processing

        Returns:
            Dict[str, Any]: OCR settings dictionary
        """
        # Use config's get_ocr_settings if available, otherwise fallback to local implementation
        if hasattr(config, "get_ocr_settings"):
            return config.get_ocr_settings(mode, lang)

        # Fallback implementation
        base_settings = {
            "deskew": True,
            "output_type": "pdfa",
            "progress_bar": True,
            "skip_big": False,
            "clean": True,
            "lang": lang,
            "clean_final": True,
            "oversample": 300,
            "jobs": min(
                config.max_concurrent_jobs
                if hasattr(config, "max_concurrent_jobs")
                else 4,
                os.cpu_count() or 1,
            ),
            "tesseract_config": "--psm 3",
        }

        if mode == "cli":
            base_settings.update({"force_ocr": False, "skip_text": True})
        elif mode == "force":
            base_settings.update({"force_ocr": True, "skip_text": False})
        elif mode == "visual":
            base_settings.update({"force_ocr": False, "skip_text": True})
        else:
            raise ValueError(f"Unknown mode: {mode}")

        return base_settings

    @staticmethod
    def visualize_hocr(
        hocr_path: Path, original_pdf: Path, vis_output_folder: Path
    ) -> None:
        """Generate visual highlights from HOCR file.

        Args:
            hocr_path: Path to HOCR file
            original_pdf: Path to original PDF
            vis_output_folder: Output folder for visual highlights
        """
        try:
            print("🖼️ Generating visual highlight from HOCR...")

            doc = fitz.open(original_pdf)
            soup = BeautifulSoup(hocr_path.read_text(encoding="utf-8"), "html.parser")

            words = soup.find_all("span", class_="ocrx_word")
            coords_per_page = {}

            for word in words:
                if "title" in word.attrs:
                    title_attr = word["title"]
                    if isinstance(title_attr, str):
                        parts = title_attr.split(";")
                        bbox = parts[0].replace("bbox", "").strip()
                        coords = list(map(int, bbox.split()))
                        parent = word.parent
                        if parent and "id" in parent.attrs:
                            id_attr = parent["id"]
                            if isinstance(id_attr, str):
                                page_num = int(id_attr.split("_")[-1])
                                coords_per_page.setdefault(page_num, []).append(coords)

            FileUtils.ensure_dir(vis_output_folder)

            for page_num, coords_list in coords_per_page.items():
                if page_num >= len(doc):
                    continue

                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
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

            if log_manager and log_manager.logger:
                log_manager.logger.info(
                    "HOCR visualization completed",
                    hocr_path=str(hocr_path),
                    pdf_path=str(original_pdf),
                    output_folder=str(vis_output_folder),
                    pages_processed=len(coords_per_page),
                    event_type="hocr_visualization_complete",
                )

        except Exception as e:
            error_handler = get_error_handler(config)
            error_handler.handle_error(
                e,
                ErrorContext(
                    operation="visualize_hocr",
                    file_path=str(hocr_path),
                    metadata={
                        "original_pdf": str(original_pdf),
                        "vis_output_folder": str(vis_output_folder),
                    },
                ),
            )
            raise

    @staticmethod
    def ocr_process(
        pdf_file: Path,
        output_base: Path,
        mode: str,
        lang: str = "heb+eng",
        archive_dir: Optional[Path] = None,
    ) -> bool:
        """Process a PDF file with OCR based on specified mode.

        Args:
            pdf_file: Input PDF file
            output_base: Base output directory
            mode: OCR processing mode
            lang: Language for OCR
            archive_dir: Optional archive directory

        Returns:
            bool: True if processing succeeded, False otherwise
        """
        try:
            FileUtils.ensure_dir(output_base)

            # Archive original file if archive directory is specified
            if archive_dir:
                FileUtils.archive_file(pdf_file, archive_dir)

            # Define output files
            pdf_output = output_base / "ocr_output.pdf"
            sidecar_txt = output_base / "ocr_output.txt"
            log_file = output_base / "ocr_log.txt"

            # Get OCR settings for the mode
            ocr_settings = OCRUtils.get_ocr_settings(mode, lang)

            # Set up logging for this file
            file_logger = logging.getLogger(f"ocr_process_{pdf_file.stem}")
            file_logger.setLevel(logging.INFO)

            # Remove any existing handlers to avoid duplicates
            for handler in file_logger.handlers[:]:
                file_logger.removeHandler(handler)

            # Add file handler for this specific file
            handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            file_logger.addHandler(handler)

            print(f"🔄 Processing: {pdf_file.name}")

            # Run OCR using ocrmypdf as a library
            ocrmypdf.ocr(pdf_file, pdf_output, sidecar=sidecar_txt, **ocr_settings)

            print(f"✅ OCR completed for {pdf_file.name}")
            print(f"📄 PDF with OCR: {pdf_output}")
            print(f"📝 Extracted text: {sidecar_txt}")
            print(f"📜 Log file: {log_file}")

            # Create zip file for force mode
            if mode == "force":
                FileUtils.zip_folder(output_base)

            file_logger.info(f"Successfully processed {pdf_file.name}")

            if log_manager and log_manager.logger:
                log_manager.logger.info(
                    "OCR processing completed",
                    pdf_file=str(pdf_file),
                    output_base=str(output_base),
                    mode=mode,
                    language=lang,
                    event_type="ocr_processing_complete",
                )

            return True

        except PriorOcrFoundError:
            print(f"⚠️ Skipping {pdf_file.name} - already contains OCR text")
            if log_manager and log_manager.logger:
                log_manager.logger.info(
                    "OCR skipped - already contains text",
                    pdf_file=str(pdf_file),
                    event_type="ocr_skipped_existing",
                )
            return False
        except InputFileError as e:
            print(f"❌ Input file error for {pdf_file.name}: {e}")
            if log_manager and log_manager.logger:
                log_manager.logger.error(
                    "OCR input file error",
                    pdf_file=str(pdf_file),
                    error=str(e),
                    event_type="ocr_input_error",
                )
            return False
        except Exception as e:
            print(f"❌ Error processing {pdf_file.name}: {e}")
            if log_manager and log_manager.logger:
                log_manager.logger.error(
                    "OCR processing error",
                    pdf_file=str(pdf_file),
                    error=str(e),
                    event_type="ocr_processing_error",
                )
            return False


class InputProcessor:
    """Input validation and processing utilities"""

    @staticmethod
    def validate_input_path(input_path: Path) -> bool:
        """Validate input path for OCR processing.

        Args:
            input_path: Path to validate

        Returns:
            bool: True if valid, False otherwise
        """
        if input_path.is_file() and input_path.suffix.lower() == ".pdf":
            return True
        elif input_path.is_dir():
            pdfs = list(input_path.glob("*.pdf"))
            return len(pdfs) > 0
        return False

    @staticmethod
    def collect_pdf_files(input_path: Path, recursive: bool = True) -> List[Path]:
        """Collect PDF files from input path.

        Args:
            input_path: Input path (file or directory)
            recursive: Whether to search recursively in directories

        Returns:
            List[Path]: List of PDF files
        """
        if input_path.is_file() and input_path.suffix.lower() == ".pdf":
            return [input_path]
        elif input_path.is_dir():
            if recursive:
                return list(input_path.glob("**/*.pdf"))
            else:
                return list(input_path.glob("*.pdf"))
        else:
            raise ValidationError(f"Invalid input path: {input_path}")

    @staticmethod
    def process_input(
        input_path: Path,
        mode: str,
        lang: str = "heb+eng",
        archive_dir: Optional[Path] = None,
        recursive: bool = True,
    ) -> tuple[int, int]:
        """Process a single PDF file or all PDFs in a directory.

        Args:
            input_path: Input path to process
            mode: OCR processing mode
            lang: Language for OCR
            archive_dir: Optional archive directory
            recursive: Whether to process directories recursively

        Returns:
            tuple[int, int]: (processed_count, skipped_count)
        """
        try:
            pdfs = InputProcessor.collect_pdf_files(input_path, recursive)

            if not pdfs:
                print(f"❌ No PDF files found in directory: {input_path}")
                return 0, 0

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            processed_count = 0
            skipped_count = 0

            for pdf in pdfs:
                print(f"\n🔄 Processing: {pdf.name}")
                base = Path(f"ocr_{mode}") / f"{pdf.stem}_{timestamp}"
                success = OCRUtils.ocr_process(pdf, base, mode, lang, archive_dir)
                if success:
                    processed_count += 1
                else:
                    skipped_count += 1

            print("\n🎉 Processing completed!")
            print(f"📊 Processed: {processed_count} files")
            print(f"⏭️ Skipped: {skipped_count} files")

            if log_manager and log_manager.logger:
                log_manager.logger.info(
                    "Batch processing completed",
                    input_path=str(input_path),
                    mode=mode,
                    language=lang,
                    processed_count=processed_count,
                    skipped_count=skipped_count,
                    total_files=len(pdfs),
                    event_type="batch_processing_complete",
                )

            return processed_count, skipped_count

        except Exception as e:
            error_handler = get_error_handler(config)
            error_handler.handle_error(
                e,
                ErrorContext(
                    operation="process_input",
                    file_path=str(input_path),
                    metadata={"mode": mode, "language": lang},
                ),
            )
            raise
