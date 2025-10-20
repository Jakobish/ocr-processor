# OCR Processing Suite

A comprehensive PDF OCR processing toolkit that combines multiple OCR approaches into a unified, feature-rich solution for document digitization and analysis.

## 🖥️ Available Interfaces

- **📟 Command Line Interface**: `pdf-ocr-processor.py` - Full-featured CLI for automation and scripting
- **🖼️ Graphical User Interface**: `pdf_ocr_gui.py` - User-friendly GUI for interactive processing

## 🎯 Overview

This OCR suite provides advanced PDF text extraction and processing capabilities with support for multiple languages (including Hebrew and English), visual highlighting, and comprehensive output formats. Built on top of OCRmyPDF, it offers both simple and advanced processing modes for various use cases.

## ✨ Key Features

### 🔧 Multiple Processing Modes
- **CLI Mode** (`--mode cli`): Fast processing that preserves existing text
- **Force Mode** (`--mode force`): Complete OCR processing with visual highlights and compression
- **Visual Mode** (`--mode visual`): Processing with visual bounding box overlays

### 📁 Flexible Input Processing
- **Single File**: Process individual PDF documents
- **Directory Processing**: Batch process entire folders
- **Recursive Search**: Automatically find PDFs in subdirectories
- **Smart Filtering**: Only processes PDF files

### 🖼️ Visual Analysis Features
- **HOCR Generation**: Extract spatial layout information
- **Bounding Box Visualization**: Generate highlighted page images
- **Sidecar Text Output**: Plain text extraction alongside PDF processing

### 📦 Advanced Output Management
- **PDF/A Format**: Standards-compliant archival output
- **Timestamped Folders**: Organized results with unique timestamps
- **Comprehensive Logging**: Detailed processing logs per file
- **Optional Archiving**: Backup original files before processing
- **ZIP Compression**: Automatic packaging for force mode

### 🌍 Multi-language Support
- **Hebrew + English** (default): `heb+eng`
- **English Only**: `eng`
- **Custom Languages**: Support for any Tesseract language pack

## 📋 Requirements

### System Dependencies
```bash
# macOS/Linux
sudo apt-get install tesseract-ocr  # Ubuntu/Debian
sudo apt-get install tesseract-ocr-heb  # Hebrew language pack
brew install tesseract  # macOS
```

### Python Packages
```bash
# Easy installation - all dependencies at once
pip install -r requirements.txt

# Or install individually if preferred
pip install ocrmypdf
pip install beautifulsoup4
pip install Pillow
pip install PyMuPDF
```

### Recommended Additional Tools
```bash
# For better PDF processing
pip install qpdf

# For enhanced image processing
pip install numpy opencv-python
```

## 🚀 Quick Start

### Command Line Interface
```bash
# Process a single PDF (CLI mode - default)
python pdf-ocr-processor.py document.pdf

# Process with force mode (complete OCR)
python pdf-ocr-processor.py --mode force document.pdf

# Process with visual highlights
python pdf-ocr-processor.py --mode visual document.pdf
```

### Graphical User Interface
```bash
# Launch the GUI
python pdf_ocr_gui.py
```

### Directory Processing
```bash
# Process all PDFs in a directory recursively
python pdf-ocr-processor.py --mode force documents/

# Process only top-level PDFs (non-recursive)
python pdf-ocr-processor.py --mode force --no-recursive documents/

# Process with archiving
python pdf-ocr-processor.py --mode force --archive-dir ./backup documents/
```

### Language Selection
```bash
# English only
python pdf-ocr-processor.py --lang eng document.pdf

# Hebrew and English (default)
python pdf-ocr-processor.py --lang heb+eng document.pdf

# Multiple languages
python pdf-ocr-processor.py --lang eng+fra+deu document.pdf
```

## 🖼️ Graphical User Interface

The GUI provides an intuitive, user-friendly interface for all OCR processing operations:

### Launching the GUI
```bash
python pdf_ocr_gui.py
```

### GUI Features

#### **📁 Input Selection**
- **File Browser**: Select individual PDF files with file dialog
- **Directory Browser**: Choose folders for batch processing
- **Drag & Drop Ready**: Easy file selection interface

#### **⚙️ Processing Options**
- **Mode Selection**: Dropdown for CLI, Force, and Visual modes
- **Dynamic Descriptions**: Mode descriptions update based on selection
- **Language Dropdown**: Support for multiple language combinations
- **Archive Toggle**: Enable/disable original file archiving
- **Archive Directory**: Browse and select archive location
- **Recursive Toggle**: Enable/disable subdirectory processing

#### **📊 Progress Tracking**
- **Real-time Progress Bar**: Visual progress indication
- **Status Updates**: Current operation status display
- **Live Statistics**: Files processed vs skipped counters
- **Processing Log**: Detailed activity log with timestamps

#### **🛠️ Control Features**
- **Start/Cancel Buttons**: Control processing operations
- **Log Management**: Save log to file or clear display
- **Tabbed Interface**: Separate tabs for processing and log viewing

### GUI Workflow

1. **Select Input**: Choose PDF file(s) or directory
2. **Configure Options**: Set processing mode, language, and archiving
3. **Start Processing**: Click start and monitor progress
4. **View Results**: Check log tab for detailed information
5. **Manage Output**: Access processed files in timestamped folders

### GUI Advantages

- **No Command Line Knowledge Required**: Point-and-click interface
- **Visual Progress Feedback**: Real-time status and progress bars
- **Error Handling**: User-friendly error messages and dialogs
- **Log Management**: Easy log viewing and saving
- **Intuitive Controls**: Self-explanatory interface elements

## 📖 Detailed Usage

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `input_path` | PDF file or directory to process | **Required** |
| `--mode` | Processing mode: `cli`, `force`, `visual` | `cli` |
| `--lang` | Language(s) for OCR | `heb+eng` |
| `--archive-dir` | Directory to backup original files | `None` |
| `--no-recursive` | Disable recursive directory search | `False` |
| `--log-file` | Main log file path | `ocr_combined.log` |

### Processing Modes Explained

#### CLI Mode (`--mode cli`)
- **Speed**: Fastest processing mode
- **Behavior**: Skips existing text, preserves layout
- **Output**: PDF with OCR enhancement, text sidecar, HOCR file
- **Use Case**: When you want to add OCR to text-light PDFs quickly

#### Force Mode (`--mode force`)
- **Speed**: Slower but thorough
- **Behavior**: Forces OCR on all pages, even those with existing text
- **Output**: All CLI mode outputs + visual highlights + ZIP archive
- **Use Case**: When you need complete text replacement or visual analysis

#### Visual Mode (`--mode visual`)
- **Speed**: Moderate processing speed
- **Behavior**: Creates visual highlights without forced OCR
- **Output**: All CLI mode outputs + visual highlights (no ZIP)
- **Use Case**: When you need to visualize text regions without full reprocessing

## 📁 Output Structure

Each processing run creates a timestamped folder structure:

```
ocr_force/
└── document_name_20231201_143022/
    ├── ocr_output.pdf      # OCR-enhanced PDF (PDF/A format)
    ├── ocr_output.txt      # Extracted plain text
    ├── ocr_output.hocr     # HOCR layout information
    ├── ocr_log.txt         # Processing log
    ├── visual/             # Visual highlight images
    │   ├── page_001.png
    │   ├── page_002.png
    │   └── ...
    └── document_name_20231201_143022.zip  # Compressed archive
```

## 🔍 Advanced Features

### Archiving Original Files
```bash
# Archive originals before processing
python pdf-ocr-processor.py --mode force --archive-dir ./originals/ documents/

# Archive structure mirrors source structure
./originals/
└── documents/
    └── archived_file.pdf
```

### Custom Logging
```bash
# Specify custom log file location
python pdf-ocr-processor.py --log-file ./logs/processing.log document.pdf

# Each processed file gets its own log in the output folder
```

### Processing Large Directories
```bash
# Process with progress tracking
python pdf-ocr-processor.py --mode force large_document_collection/

# Monitor progress in both console and log files
```

## 🛠️ Troubleshooting

### Common Issues

#### Missing Dependencies
```bash
# Install all required packages at once
pip install -r requirements.txt

# Or install individually if needed
pip install ocrmypdf beautifulsoup4 Pillow PyMuPDF

# GUI Requirements (already included in CLI requirements)
# tkinter is included with Python by default and doesn't need installation
```

#### Requirements.txt File
The `requirements.txt` file in this directory contains all necessary Python dependencies with version specifications for optimal compatibility. Use `pip install -r requirements.txt` for the easiest setup.

#### Tesseract Not Found
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-heb

# macOS
brew install tesseract tesseract-lang

# Verify installation
tesseract --version
```

#### Permission Errors
```bash
# Check file permissions
chmod 644 input.pdf

# Run with appropriate permissions
python pdf-ocr-processor.py --mode force /path/to/documents/
```

#### Large File Processing
```bash
# For very large PDFs, consider:
# 1. Using CLI mode for faster processing
# 2. Processing files individually
# 3. Checking available disk space
```

### Performance Optimization

#### For Faster Processing
- Use `--mode cli` for existing text documents
- Disable recursive search with `--no-recursive` for flat directories
- Process files individually rather than in large batches

#### For Better Quality
- Use `--mode force` for complete text replacement
- Ensure proper language packs are installed
- Check OCR settings in the script configuration

## 📊 Processing Statistics

The tool provides detailed statistics:
- **Processed Files**: Successfully OCR'd documents
- **Skipped Files**: Files already containing OCR text
- **Error Files**: Files that failed processing with specific error details

## 🔧 Configuration

### Default OCR Settings
- **Page Segmentation Mode**: `--psm 3` (automatic page segmentation)
- **DPI Oversampling**: 300 DPI for better quality
- **Output Format**: PDF/A for archival compliance
- **Image Optimization**: Enabled for smaller file sizes

### Customizing OCR Behavior

The script uses sensible defaults but can be modified by editing the `get_ocr_settings()` function in the source code for advanced use cases.

## 📝 Use Cases

### Document Digitization
- Convert scanned documents to searchable PDFs
- Process archival materials
- Create accessible documents from images

### Forensic Analysis
- Extract text for investigation purposes
- Analyze document structure and layout
- Create visual representations of text regions

### Batch Processing
- Process large collections of documents
- Automate document conversion workflows
- Archive and organize document collections

### Multi-language Documents
- Process Hebrew/English mixed documents
- Handle international document collections
- Support for custom language combinations

## 🤝 Contributing

This OCR suite is designed to be extensible. Common customization points:

1. **Language Support**: Add new language packs in `get_ocr_settings()`
2. **Output Formats**: Modify output file generation
3. **Processing Modes**: Add new processing modes as needed
4. **Visual Features**: Enhance the visual highlighting system

## 📄 License

This OCR processing suite is part of the VirtualBox Technologies toolkit and is available for use in document processing workflows.

---

**For support or questions, please contact the development team or create an issue in the project repository.**