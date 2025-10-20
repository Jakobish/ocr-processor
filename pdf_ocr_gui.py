#!/usr/bin/env python3
"""
PDF OCR Processor - GUI Version

A graphical user interface for the comprehensive PDF OCR processing toolkit.
Provides an intuitive interface for all OCR operations including multiple modes,
language selection, archiving, and visual processing options.
"""

import os
import sys
import shutil
import logging
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import zipfile
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
import fitz  # PyMuPDF
import ocrmypdf
from ocrmypdf.exceptions import InputFileError, PriorOcrFoundError

class PDFOCRGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF OCR Processor")
        self.root.geometry("800x700")
        self.root.resizable(True, True)

        # Processing state
        self.processing = False
        self.cancel_processing = False

        # Core functionality (reused from command-line version)
        self.ensure_dir = lambda path: path.mkdir(parents=True, exist_ok=True)
        self.zip_folder = self._zip_folder
        self.visualize_hocr = self._visualize_hocr
        self.get_ocr_settings = self._get_ocr_settings
        self.ocr_process = self._ocr_process
        self.process_input = self._process_input

        self.setup_gui()
        self.setup_logging()

    def setup_gui(self):
        """Set up the graphical user interface."""
        # Create main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Main processing tab
        self.main_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.main_frame, text="OCR Processing")

        # Log tab
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="Processing Log")

        self.create_main_tab()
        self.create_log_tab()

    def create_main_tab(self):
        """Create the main processing interface."""
        # File Selection Frame
        file_frame = ttk.LabelFrame(self.main_frame, text="Input Selection", padding=10)
        file_frame.pack(fill=tk.X, padx=10, pady=5)

        # File/Directory selection
        ttk.Label(file_frame, text="PDF File or Directory:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.input_path = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.input_path, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_input).grid(row=0, column=2, padx=5, pady=5)

        # Processing Options Frame
        options_frame = ttk.LabelFrame(self.main_frame, text="Processing Options", padding=10)
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        # Mode selection
        ttk.Label(options_frame, text="OCR Mode:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.mode = tk.StringVar(value="cli")
        mode_combo = ttk.Combobox(options_frame, textvariable=self.mode, width=15)
        mode_combo['values'] = ('cli', 'force', 'visual')
        mode_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        mode_combo.bind('<<ComboboxSelected>>', self.update_mode_description)

        # Mode description
        self.mode_description = tk.StringVar(value="Fast processing, preserves existing text")
        ttk.Label(options_frame, textvariable=self.mode_description).grid(row=0, column=2, sticky=tk.W, padx=10, pady=5)

        # Language selection
        ttk.Label(options_frame, text="Language:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.language = tk.StringVar(value="heb+eng")
        lang_combo = ttk.Combobox(options_frame, textvariable=self.language, width=15)
        lang_combo['values'] = ('heb+eng', 'eng', 'heb', 'eng+fra', 'eng+deu', 'eng+spa')
        lang_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # Archive options
        self.archive_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Archive original files",
                       variable=self.archive_enabled).grid(row=2, column=0, sticky=tk.W, pady=5)

        ttk.Label(options_frame, text="Archive Directory:").grid(row=2, column=1, sticky=tk.W, pady=5)
        self.archive_path = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.archive_path, width=30).grid(row=2, column=2, padx=5, pady=5)
        ttk.Button(options_frame, text="Browse", command=self.browse_archive).grid(row=2, column=3, padx=5, pady=5)

        # Recursive processing
        self.recursive = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Recursive directory search",
                       variable=self.recursive).grid(row=3, column=0, sticky=tk.W, pady=5)

        # Progress Frame
        progress_frame = ttk.LabelFrame(self.main_frame, text="Progress", padding=10)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.status_var).pack(pady=5)

        # Control Buttons Frame
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        self.start_button = ttk.Button(button_frame, text="Start Processing", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_processing,
                                       state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="Clear Log", command=self.clear_log).pack(side=tk.RIGHT, padx=5)

        # Statistics
        self.stats_var = tk.StringVar(value="Files processed: 0 | Skipped: 0")
        ttk.Label(self.main_frame, textvariable=self.stats_var).pack(pady=5)

    def create_log_tab(self):
        """Create the log viewing interface."""
        # Log display
        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Log control buttons
        log_button_frame = ttk.Frame(self.log_frame)
        log_button_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(log_button_frame, text="Save Log", command=self.save_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_button_frame, text="Clear Display", command=self.clear_log).pack(side=tk.RIGHT, padx=5)

    def setup_logging(self):
        """Set up logging to display in GUI."""
        self.log_handler = GUIHandler(self.update_log_display)

        # Configure root logger
        logging.getLogger().addHandler(self.log_handler)
        logging.getLogger().setLevel(logging.INFO)

    def browse_input(self):
        """Browse for input file or directory."""
        if self.mode.get() == "single":
            path = filedialog.askopenfilename(title="Select PDF File",
                                            filetypes=[("PDF files", "*.pdf")])
        else:
            path = filedialog.askdirectory(title="Select Directory")

        if path:
            self.input_path.set(path)

    def browse_archive(self):
        """Browse for archive directory."""
        path = filedialog.askdirectory(title="Select Archive Directory")
        if path:
            self.archive_path.set(path)

    def update_mode_description(self, event=None):
        """Update mode description based on selection."""
        descriptions = {
            'cli': 'Fast processing, preserves existing text',
            'force': 'Complete OCR with visual highlights and compression',
            'visual': 'Processing with visual highlights (no compression)'
        }
        self.mode_description.set(descriptions.get(self.mode.get(), ''))

    def start_processing(self):
        """Start OCR processing in a separate thread."""
        if not self.input_path.get():
            messagebox.showerror("Error", "Please select an input file or directory.")
            return

        if self.archive_enabled.get() and not self.archive_path.get():
            messagebox.showerror("Error", "Please specify an archive directory.")
            return

        self.processing = True
        self.cancel_processing = False

        # Update UI
        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.progress_var.set(0)
        self.status_var.set("Initializing...")

        # Start processing thread
        process_thread = threading.Thread(target=self.run_processing, daemon=True)
        process_thread.start()

    def cancel_processing(self):
        """Cancel ongoing processing."""
        self.cancel_processing = True
        self.status_var.set("Cancelling...")

    def run_processing(self):
        """Run OCR processing (called in separate thread)."""
        try:
            # Import here to avoid GUI blocking during import
            import filecmp

            # Reinitialize core functions with proper imports
            self.filecompare = lambda a, b: filecmp.cmp(a, b, shallow=True) if os.path.exists(b) else False

            # Set up main logging
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(levelname)s - %(message)s",
                handlers=[logging.StreamHandler(sys.stdout)]
            )

            ocrmypdf.configure_logging(ocrmypdf.Verbosity.default)

            self.status_var.set("Processing started...")
            self.log_message("🚀 Starting OCR processing...")

            # Process the input
            processed, skipped = self._process_input(
                Path(self.input_path.get()),
                self.mode.get(),
                self.language.get(),
                Path(self.archive_path.get()) if self.archive_enabled.get() else None,
                self.recursive.get()
            )

            # Update statistics
            self.stats_var.set(f"Files processed: {processed} | Skipped: {skipped}")

            if not self.cancel_processing:
                self.status_var.set("Processing completed successfully!")
                self.log_message("🎉 Processing completed!")
            else:
                self.status_var.set("Processing cancelled.")
                self.log_message("⚠️ Processing cancelled by user.")

        except Exception as e:
            self.log_message(f"❌ Error during processing: {str(e)}")
            self.status_var.set("Error occurred")
            messagebox.showerror("Processing Error", str(e))
        finally:
            self.processing = False
            self.start_button.config(state=tk.NORMAL)
            self.cancel_button.config(state=tk.DISABLED)

    def log_message(self, message):
        """Add message to log display."""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def clear_log(self):
        """Clear the log display."""
        self.log_text.delete(1.0, tk.END)

    def save_log(self):
        """Save log to file."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.log_text.get(1.0, tk.END))

    def update_log_display(self, message):
        """Update log display from logging thread."""
        self.log_text.after_idle(lambda: self.log_message(message))

    # Core functionality methods (adapted from command-line version)
    def _zip_folder(self, folder_path: Path):
        """Create a zip file from a folder."""
        zip_path = folder_path.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for path in folder_path.rglob("*"):
                if path.is_file():
                    zipf.write(path, arcname=path.relative_to(folder_path))
        self.log_message(f"📦 Output zipped to: {zip_path.name}")

    def _visualize_hocr(self, hocr_path: Path, original_pdf: Path, vis_output_folder: Path):
        """Generate visual highlights from HOCR file."""
        self.log_message("🖼️ Generating visual highlight from HOCR...")
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

        self.ensure_dir(vis_output_folder)

        for page_num, coords_list in coords_per_page.items():
            if page_num >= len(doc):
                continue

            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            draw = ImageDraw.Draw(img)

            for box in coords_list:
                if len(box) >= 4:
                    x1, y1, x2, y2 = box[:4]
                    draw.rectangle([x1, y1, x2, y2], outline="red", width=2)

            output_path = vis_output_folder / f"page_{page_num + 1:03d}.png"
            img.save(output_path)

        self.log_message(f"📸 Highlighted images saved in: {vis_output_folder}")

    def _get_ocr_settings(self, mode: str, lang: str = "heb+eng"):
        """Get OCR settings based on mode."""
        base_settings = {
            'deskew': True,
            'output_type': 'pdfa',
            'progress_bar': False,  # Disable for GUI
            'skip_big': False,
            'fast_web_view': True,
            'optimize_images': True,
            'clean': True,
            'lang': lang,
            'clean_final': True,
            'oversample': 300,
            'jobs': 0,
            'tesseract_config': '--psm 3',
        }

        if mode == "cli":
            base_settings.update({'force_ocr': False, 'skip_text': True})
        elif mode == "force":
            base_settings.update({'force_ocr': True, 'skip_text': False})
        elif mode == "visual":
            base_settings.update({'force_ocr': False, 'skip_text': True})

        return base_settings

    def _ocr_process(self, pdf_file: Path, output_base: Path, mode: str, lang: str = "heb+eng", archive_dir: Path = None):
        """Process a PDF file with OCR based on specified mode."""
        self.ensure_dir(output_base)

        # Archive original file if needed
        if archive_dir:
            archive_filename = archive_dir / pdf_file.relative_to(pdf_file.parent.parent)
            if not self.filecompare(pdf_file, archive_filename):
                self.log_message(f"📁 Archiving original file to: {archive_filename}")
                try:
                    archive_filename.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(pdf_file, archive_filename)
                except OSError:
                    archive_filename.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(pdf_file, archive_filename)

        # Define output files
        pdf_output = output_base / "ocr_output.pdf"
        sidecar_txt = output_base / "ocr_output.txt"
        hocr_output = output_base / "ocr_output.hocr"
        log_file = output_base / "ocr_log.txt"

        # Get OCR settings
        ocr_settings = self.get_ocr_settings(mode, lang)

        # Set up logging for this file
        file_logger = logging.getLogger(f"ocr_process_{pdf_file.stem}")
        handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        file_logger.addHandler(handler)
        file_logger.setLevel(logging.INFO)

        try:
            self.log_message(f"🔄 Processing: {pdf_file.name}")

            # Run OCR
            ocrmypdf.ocr(
                pdf_file, pdf_output,
                sidecar=sidecar_txt, hocr=hocr_output,
                **ocr_settings
            )

            self.log_message(f"✅ OCR completed for {pdf_file.name}")
            self.log_message(f"📄 PDF with OCR: {pdf_output}")
            self.log_message(f"📝 Extracted text: {sidecar_txt}")
            self.log_message(f"📐 HOCR layout: {hocr_output}")
            self.log_message(f"📜 Log file: {log_file}")

            # Generate visual highlights for force and visual modes
            if mode in ["force", "visual"] and hocr_output.exists():
                vis_folder = output_base / "visual"
                self.visualize_hocr(hocr_output, pdf_file, vis_folder)

            # Create zip file for force mode
            if mode == "force":
                self.zip_folder(output_base)

            file_logger.info(f"Successfully processed {pdf_file.name}")
            return True

        except PriorOcrFoundError:
            self.log_message(f"⚠️ Skipping {pdf_file.name} - already contains OCR text")
            return False
        except InputFileError as e:
            self.log_message(f"❌ Input file error for {pdf_file.name}: {e}")
            return False
        except Exception as e:
            self.log_message(f"❌ Error processing {pdf_file.name}: {e}")
            return False

    def _process_input(self, input_path: Path, mode: str, lang: str = "heb+eng", archive_dir: Path = None, recursive: bool = True):
        """Process a single PDF file or all PDFs in a directory."""
        if input_path.is_file() and input_path.suffix.lower() == ".pdf":
            pdfs = [input_path]
        elif input_path.is_dir():
            if recursive:
                pdfs = list(input_path.glob("**/*.pdf"))
            else:
                pdfs = list(input_path.glob("*.pdf"))

            if not pdfs:
                self.log_message(f"❌ No PDF files found in directory: {input_path}")
                return 0, 0
        else:
            self.log_message("❌ Invalid input. Provide PDF file or folder containing PDFs.")
            return 0, 0

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        processed_count = 0
        skipped_count = 0

        total_files = len(pdfs)

        for i, pdf in enumerate(pdfs):
            if self.cancel_processing:
                break

            self.log_message(f"\n🔄 Processing: {pdf.name}")
            base = Path(f"ocr_{mode}") / f"{pdf.stem}_{timestamp}"
            success = self.ocr_process(pdf, base, mode, lang, archive_dir)

            if success:
                processed_count += 1
            else:
                skipped_count += 1

            # Update progress
            progress = ((i + 1) / total_files) * 100
            self.progress_var.set(progress)

        self.log_message("\n🎉 Processing completed!")
        self.log_message(f"📊 Processed: {processed_count} files")
        self.log_message(f"⏭️ Skipped: {skipped_count} files")

        return processed_count, skipped_count

class GUIHandler(logging.Handler):
    """Custom logging handler for GUI."""
    def __init__(self, gui_callback):
        super().__init__()
        self.gui_callback = gui_callback

    def emit(self, record):
        message = self.format(record)
        if self.gui_callback:
            self.gui_callback(message)

def main():
    root = tk.Tk()
    PDFOCRGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()