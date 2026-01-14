#!/usr/bin/env python3
"""
PDF OCR Processor - Simple GUI Version

A simplified graphical user interface for PDF OCR processing.
Creates OCR versions side by side with original files.
"""

import sys
import logging
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path



class PDFOCRGUISimple:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF OCR Processor - Simple")
        self.root.geometry("800x700")
        self.root.resizable(True, True)

        # Processing state
        self.processing = False
        self.cancel_requested = False

        # Core functionality
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

        # Mode is fixed to cli for simplicity
        self.mode = tk.StringVar(value="cli")

        # Language selection
        ttk.Label(options_frame, text="Language:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.language = tk.StringVar(value="heb+eng")
        lang_combo = ttk.Combobox(options_frame, textvariable=self.language, width=15)
        lang_combo['values'] = ('script/Hebrew+heb+eng','heb+eng', 'script/Hebrew+heb', 'eng+script/Hebrew+heb', 'eng+heb', 'eng+deu', )
        lang_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # Recursive processing
        self.recursive = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Recursive directory search",
                       variable=self.recursive).grid(row=2, column=0, sticky=tk.W, pady=5)

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
        path = filedialog.askdirectory(title="Select Directory")
        if path:
            self.input_path.set(path)



    def start_processing(self):
        """Start OCR processing in a separate thread."""
        if not str(self.input_path.get()).strip():
            messagebox.showerror("Error", "Please select an input file or directory.")
            return

        self.processing = True
        self.cancel_requested = False

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
        self.cancel_requested = True
        self.status_var.set("Cancelling...")

    def run_processing(self):
        """Run OCR processing (called in separate thread)."""
        try:
            # Set up main logging
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(levelname)s - %(message)s",
                handlers=[logging.StreamHandler(sys.stdout)]
            )



            self.status_var.set("Processing started...")
            self.log_message("🚀 Starting OCR processing...")

            # Process the input
            processed, skipped = self._process_input(
                Path(self.input_path.get()),
                self.language.get(),
                self.recursive.get()
            )

            # Update statistics
            self.stats_var.set(f"Files processed: {processed} | Skipped: {skipped}")

            if not self.cancel_requested:
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

    # Core functionality methods
    def _ocr_process(self, pdf_file: Path, lang: str = "heb+eng"):
        """Process a PDF file with OCR."""
        # Ensure lang is string
        lang = str(lang)

        # Define output files
        pdf_output = pdf_file.with_name(pdf_file.stem + ".ocr.pdf")
        sidecar_txt = pdf_file.with_name(pdf_file.name + ".sidecar.txt")
        log_file = pdf_file.with_name(pdf_file.stem + ".log.txt")

        # Build ocrmypdf command
        command = [
            "ocrmypdf",
            "--redo-ocr",
            "--lang", lang,
            "--oversample", "300",
            "--jobs", "0",
            "--optimize-images", "0",
            str(pdf_file),
            str(pdf_output),
            "--sidecar", str(sidecar_txt)
        ]

        try:
            self.log_message(f"🔄 Processing: {pdf_file.name}")

            # Run OCR and capture all output to log file
            with log_file.open('a', encoding='utf-8') as f:
                result = subprocess.run(command, stdout=f, stderr=subprocess.STDOUT, text=True)

            if result.returncode == 0:
                self.log_message(f"✅ OCR completed for {pdf_file.name}")
                self.log_message(f"📄 PDF with OCR: {pdf_output}")
                self.log_message(f"📝 Extracted text: {sidecar_txt}")
                self.log_message(f"📜 Log file: {log_file}")
                return True
            else:
                self.log_message(f"❌ Error processing {pdf_file.name}: OCR failed with return code {result.returncode}")
                return False

        except Exception as e:
            self.log_message(f"❌ Error processing {pdf_file.name}: {e}")
            return False

    def _process_input(self, input_path: Path, lang: str = "heb+eng", recursive: bool = True):
        """Process a single PDF file or all PDFs in a directory."""
        if input_path.is_file() and input_path.suffix.lower() == ".pdf":
            pdfs = [input_path]
        elif input_path.is_dir():
            if recursive:
                pdfs = list(input_path.glob("**/*.pdf"))
            else:
                pdfs = list(input_path.glob("*.pdf"))

            # Filter out already processed .ocr.pdf files
            pdfs = [p for p in pdfs if not p.name.endswith('.ocr.pdf')]

            if not pdfs:
                self.log_message(f"❌ No PDF files found in directory: {input_path}")
                return 0, 0
        else:
            self.log_message("❌ Invalid input. Provide PDF file or folder containing PDFs.")
            return 0, 0

        processed_count = 0
        skipped_count = 0

        total_files = len(pdfs)

        for i, pdf in enumerate(pdfs):
            if self.cancel_requested:
                break

            self.log_message(f"\n🔄 Processing: {pdf.name}")
            success = self.ocr_process(pdf, lang)

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
    PDFOCRGUISimple(root)
    root.mainloop()

if __name__ == "__main__":
    main()