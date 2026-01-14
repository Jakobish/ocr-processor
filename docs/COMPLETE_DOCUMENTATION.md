# OCR Processor Enterprise - Complete Documentation

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Usage](#usage)
7. [API Reference](#api-reference)
8. [Development](#development)
9. [Deployment](#deployment)
10. [Administration](#administration)
11. [Troubleshooting](#troubleshooting)
12. [Security](#security)

---

## Overview

The OCR Processor Enterprise is a comprehensive PDF OCR (Optical Character Recognition) processing toolkit that combines multiple OCR approaches into a unified, feature-rich solution for document digitization and analysis. Built on top of OCRmyPDF, it offers both simple and advanced processing modes for various use cases.

### Key Capabilities

- **Multi-format Input**: Process individual PDF files or entire directories
- **Multiple Interfaces**: REST API, Command Line Interface, and Graphical User Interface
- **Multi-language Support**: Hebrew, English, and other languages via Tesseract
- **Visual Analysis**: Bounding box visualization and HOCR output
- **Enterprise Features**: Job queuing, progress tracking, notifications, and audit logging

### Version Information

- **Current Version**: 2.0.0
- **Python Support**: 3.11+
- **License**: Part of the VirtualBox Technologies toolkit

---

## Features

### Processing Modes

| Mode     | Description                                         | Use Case              |
| -------- | --------------------------------------------------- | --------------------- |
| `cli`    | Fast processing that preserves existing text        | Quick OCR enhancement |
| `force`  | Complete OCR with visual highlights and compression | Full text replacement |
| `visual` | Processing with bounding box overlays               | Layout analysis       |

### Input Processing

- **Single File**: Process individual PDF documents
- **Directory Processing**: Batch process entire folders
- **Recursive Search**: Automatically find PDFs in subdirectories
- **Smart Filtering**: Only processes PDF files

### Visual Analysis Features

- **HOCR Generation**: Extract spatial layout information
- **Bounding Box Visualization**: Generate highlighted page images
- **Sidecar Text Output**: Plain text extraction alongside PDF processing

### Output Management

- **PDF/A Format**: Standards-compliant archival output
- **Timestamped Folders**: Organized results with unique timestamps
- **Comprehensive Logging**: Detailed processing logs per file
- **Optional Archiving**: Backup original files before processing
- **ZIP Compression**: Automatic packaging for force mode

### Multi-language Support

- **Hebrew + English** (default): `heb+eng`
- **English Only**: `eng`
- **Custom Languages**: Support for any Tesseract language pack

---

## Architecture

### Project Structure

```markdown
ocr-processor/
├── src/                    # Enterprise application code
│   ├── api_server.py      # REST API server (FastAPI)
│   ├── config.py           # Configuration management
│   ├── database_manager.py # Database operations (SQLAlchemy)
│   ├── error_handler.py    # Error handling and recovery
│   ├── logger.py           # Structured logging (structlog)
│   ├── notification_manager.py # Notifications and alerts
│   ├── progress_tracker.py # Job progress tracking
│   └── security_validator.py # Input validation and security
├── cli/                    # Standalone CLI/GUI tools
│   ├── ocr_combined.py     # Main OCR processing script
│   ├── pdf_ocr_gui.py      # Graphical user interface
│   └── ...                 # Other CLI utilities
├── docker/                 # Docker configuration
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── nginx.conf
│   └── init.sql
├── docs/                   # Documentation
│   ├── ADMIN_GUIDE.md
│   └── DEPLOYMENT.md
└── tests/                  # Test files (if present)
```

### System Architecture

```markdown
┌─────────────────────────────────────────────────────────────────┐
│                        OCR Processor                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │   REST    │  │    CLI    │  │    GUI    │  │  Worker   │    │
│  │   API     │  │  Tools    │  │  Interface│  │  Process  │    │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘    │
│        │              │              │              │          │
│        └──────────────┴──────────────┴──────────────┘          │
│                            │                                     │
│                    ┌───────▼───────┐                            │
│                    │  Core Engine  │                            │
│                    │ (OCRmyPDF)    │                            │
│                    └───────┬───────┘                            │
│                            │                                     │
│    ┌───────────────────────┼───────────────────────┐            │
│    │                       │                       │            │
│ ┌───▼───┐            ┌─────▼─────┐           ┌─────▼─────┐     │
│ │ Logger│            │  Database │           │ Notifier  │     │
│ └───────┘            │  (SQL)    │           └───────────┘     │
│                      └───────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

### Component Details

#### API Server ([`api_server.py`](src/api_server.py))

The REST API server provides HTTP endpoints for:

- Job creation and management
- System status monitoring
- File upload/download
- Batch processing

Key features:

- FastAPI-based REST API
- JWT/Bearer token authentication
- CORS support
- Background task processing

#### Configuration ([`config.py`](src/config.py))

Centralized configuration management with:

- Environment variable support
- JSON config file loading
- Validation and defaults
- OCR settings per mode

#### Database Manager ([`database_manager.py`](src/database_manager.py))

SQLAlchemy-based database operations:

- Job tracking and history
- File processing records
- Audit logging
- Performance metrics

#### Error Handler ([`error_handler.py`](src/error_handler.py))

Comprehensive error handling:

- Error classification and categorization
- Exponential backoff retry mechanism
- Circuit breaker pattern
- Notification on critical errors

#### Logger ([`logger.py`](src/logger.py))

Structured logging with:

- JSON and console output
- Log rotation
- Remote logging support
- Performance metrics tracking

#### Notification Manager ([`notification_manager.py`](src/notification_manager.py))

Multi-channel notifications:

- Email (SMTP)
- Webhooks
- Slack integration
- Scheduled notifications

#### Progress Tracker ([`progress_tracker.py`](src/progress_tracker.py))

Real-time progress tracking:

- Job status updates
- Performance metrics collection
- Queue management
- Callback system

#### Security Validator ([`security_validator.py`](src/security_validator.py))

Input validation and security:

- Path traversal prevention
- File type validation
- Suspicious pattern detection
- Quarantine system

---

## Installation

### System Requirements

| Requirement | Minimum     | Recommended   |
| ----------- | ----------- | ------------- |
| OS          | Linux/macOS | Ubuntu 20.04+ |
| RAM         | 4 GB        | 8 GB          |
| Storage     | 10 GB       | 50 GB SSD     |
| CPU         | 2 cores     | 4+ cores      |

### Dependencies

#### System Dependencies

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-heb \
    qpdf \
    poppler-utils
```

**macOS:**

```bash
brew install tesseract qpdf poppler
```

#### Python Dependencies

```bash
pip install -r requirements.txt
```

### Docker Installation (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd ocr-processor

# Copy environment file
cp .env.example .env

# Start all services
docker-compose up -d

# Verify deployment
docker-compose ps
curl http://localhost:8000/health
```

### Manual Installation

```bash
# Create virtual environment
python -m venv ocr-env
source ocr-env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install system dependencies (Ubuntu/Debian)
sudo apt-get install tesseract-ocr tesseract-ocr-heb

# Start the API server
python -m src.api_server
```

---

## Configuration

### Environment Variables

| Variable                   | Description                | Default   | Required |
| -------------------------- | -------------------------- | --------- | -------- |
| `OCR_LOG_LEVEL`            | Logging level              | INFO      | No       |
| `OCR_DEFAULT_LANGUAGE`     | Default OCR language       | heb+eng   | No       |
| `OCR_DEFAULT_MODE`         | Default processing mode    | cli       | No       |
| `OCR_MAX_CONCURRENT_JOBS`  | Max parallel jobs          | 4         | No       |
| `OCR_MAX_FILE_SIZE`        | Max file size (bytes)      | 104857600 | No       |
| `OCR_TIMEOUT_PER_FILE`     | Timeout per file (seconds) | 300       | No       |
| `OCR_ENABLE_API`           | Enable REST API            | true      | No       |
| `OCR_API_HOST`             | API host                   | 0.0.0.0   | No       |
| `OCR_API_PORT`             | API port                   | 8000      | No       |
| `OCR_DATABASE_URL`         | Database connection        | -         | No\*     |
| `OCR_ENABLE_NOTIFICATIONS` | Enable notifications       | false     | No       |
| `OCR_NOTIFICATION_EMAIL`   | Admin email                | -         | No       |
| `OCR_SMTP_SERVER`          | SMTP server                | -         | No       |
| `OCR_WEBHOOK_URL`          | Webhook URL                | -         | No       |

\*Required for database features

### Configuration File

Create `ocr_config.json` in the project root:

```json
{
  "default_language": "heb+eng",
  "default_mode": "cli",
  "max_concurrent_jobs": 4,
  "max_file_size": 104857600,
  "timeout_per_file": 300,
  "archive_originals": true,
  "create_zip_archives": true,
  "enable_database": false,
  "database_url": "postgresql://user:pass@localhost/ocr_db",
  "enable_notifications": false,
  "notification_email": "",
  "smtp_server": "",
  "smtp_port": 587,
  "webhook_url": "",
  "enable_api": true,
  "api_host": "0.0.0.0",
  "api_port": 8000,
  "log_level": "INFO",
  "log_to_file": true,
  "log_directory": "logs"
}
```

### Configuration Precedence

1. Environment variables (highest priority)
2. Configuration file (`ocr_config.json`)
3. Default values (lowest priority)

---

## Usage

### Command Line Interface

#### Basic Usage

```bash
# Process a single PDF (CLI mode - default)
python cli/ocr_combined.py document.pdf

# Process with force mode (complete OCR)
python cli/ocr_combined.py --mode force document.pdf

# Process with visual mode (bounding boxes)
python cli/ocr_combined.py --mode visual document.pdf
```

#### Directory Processing

```bash
# Process all PDFs in a directory recursively
python cli/ocr_combined.py --mode force documents/

# Process only top-level PDFs (non-recursive)
python cli/ocr_combined.py --mode force --no-recursive documents/

# Process with archiving
python cli/ocr_combined.py --mode force --archive-dir ./backup documents/
```

#### Language Selection

```bash
# English only
python cli/ocr_combined.py --lang eng document.pdf

# Hebrew and English (default)
python cli/ocr_combined.py --lang heb+eng document.pdf

# Multiple languages
python cli/ocr_combined.py --lang eng+fra+deu document.pdf
```

#### Command Line Options

| Option           | Description                   | Default          |
| ---------------- | ----------------------------- | ---------------- |
| `input_path`     | PDF file or directory         | Required         |
| `--mode`         | Processing mode               | cli              |
| `--lang`         | Language(s) for OCR           | heb+eng          |
| `--archive-dir`  | Directory to backup originals | None             |
| `--no-recursive` | Disable recursive search      | False            |
| `--log-file`     | Main log file path            | ocr_combined.log |

### Graphical User Interface

Launch the GUI application:

```bash
python cli/pdf_ocr_gui.py
```

The GUI provides:

- File/directory selection
- Mode and language dropdowns
- Progress tracking
- Log viewing
- Archive configuration

### REST API

#### Base URL

```bash
http://localhost:8000/api/v1
```

#### Authentication

All API endpoints require Bearer token authentication:

```bash
curl -H "Authorization: Bearer your-api-key" http://localhost:8000/health
```

#### Endpoints

**Health Check:**

```bash
GET /health
```

**Create Job:**

```bash
POST /jobs
Content-Type: application/json

{
  "input_path": "/path/to/document.pdf",
  "mode": "cli",
  "language": "heb+eng",
  "priority": "normal",
  "recursive": true,
  "webhook_url": "https://your-webhook.com/callback"
}
```

**Get Job Status:**

```bash
GET /jobs/{job_id}
```

**List Jobs:**

```bash
GET /jobs?limit=50&offset=0
```

**Cancel Job:**

```bash
DELETE /jobs/{job_id}
```

**Upload File:**

```bash
POST /upload
Content-Type: multipart/form-data

file: document.pdf
mode: cli
language: heb+eng
priority: normal
```

---

## API Reference

### Request Models

#### OCRJobCreate

| Field               | Type    | Required | Description                              |
| ------------------- | ------- | -------- | ---------------------------------------- |
| `input_path`        | string  | Yes      | Path to PDF file or directory            |
| `mode`              | string  | No       | Processing mode (cli, force, visual)     |
| `language`          | string  | No       | Language for OCR                         |
| `priority`          | string  | No       | Job priority (low, normal, high, urgent) |
| `recursive`         | boolean | No       | Process directories recursively          |
| `archive_originals` | boolean | No       | Archive original files                   |
| `webhook_url`       | string  | No       | Webhook URL for notifications            |
| `metadata`          | object  | No       | Additional metadata                      |

#### OCRJobResponse

| Field             | Type     | Description                                                 |
|-------------------|----------|-------------------------------------------------------------|
| `job_id`          | string   | Unique job identifier                                       |
| `status`          | string   | Job status (pending, running, completed, failed, cancelled) |
| `progress`        | float    | Progress percentage (0-100)                                 |
| `input_path`      | string   | Original input path                                         |
| `mode`            | string   | Processing mode                                             |
| `language`        | string   | OCR language                                                |
| `created_at`      | datetime | Job creation timestamp                                      |
| `started_at`      | datetime | Job start timestamp                                         |
| `completed_at`    | datetime | Job completion timestamp                                    |
| `total_files`     | int      | Total files to process                                      |
| `processed_files` | int      | Successfully processed files                                |
| `failed_files`    | int      | Failed files                                                |
| `output_path`     | string   | Output directory path                                       |
| `error_message`   | string   | Error message if failed                                     |

### Response Models

#### HealthCheck

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": {
    "database": "connected",
    "storage": "writable"
  },
  "database": "healthy",
  "storage": "healthy"
}
```

#### SystemStatus

```json
{
  "status": "running",
  "version": "2.0.0",
  "uptime_seconds": 3600,
  "active_jobs": 2,
  "total_jobs": 150,
  "database_enabled": true,
  "notifications_enabled": true
}
```

### Error Responses

```json
{
  "detail": "Error message description"
}
```

**Common HTTP Status Codes:**

| Code | Description           |
| ---- | --------------------- |
| 200  | Success               |
| 201  | Created               |
| 400  | Bad Request           |
| 401  | Unauthorized          |
| 404  | Not Found             |
| 500  | Internal Server Error |

---

## Development

### Project Setup

```bash
# Clone repository
git clone <repository-url>
cd ocr-processor

# Create virtual environment
python -m venv dev-env
source dev-env/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/test_api_server.py -v
```

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all functions
- Write docstrings for public functions
- Run linting: `flake8 src/`

### Adding New Features

1. Create feature branch
2. Implement changes
3. Add tests
4. Update documentation
5. Submit pull request

### Debugging

```bash
# Enable debug logging
export OCR_LOG_LEVEL=DEBUG

# Run with Python debugger
python -m pdb src/api_server.py
```

---

## Deployment

### Docker Deployment

#### Production Setup

```bash
# Create environment file
cp .env.example .env
# Edit .env with production values

# Start services
docker-compose up -d

# Scale workers
docker-compose up -d --scale ocr-worker=3
```

#### Docker Compose Services

```yaml
services:
  ocr-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OCR_DATABASE_URL=postgresql://user:pass@postgres/ocr_db
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs

  ocr-worker:
    build: .
    scale: 3
    environment:
      - OCR_DATABASE_URL=postgresql://user:pass@postgres/ocr_db

  postgres:
    image: postgres:13
    environment:
      - POSTGRES_USER=ocr_user
      - POSTGRES_PASSWORD=ocr_password
      - POSTGRES_DB=ocr_db
    volumes:
      - postgres_data:/var/lib/postgresql/data

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf
      - ./docker/ssl:/etc/nginx/ssl
```

### Manual Deployment

#### System Requirements

- Python 3.11+
- PostgreSQL 13+
- Redis (optional, for caching)
- Nginx (reverse proxy)

#### Steps

```bash
# Create user and directories
sudo useradd -r -s /sbin/nologin ocr
sudo mkdir -p /var/log/ocr /var/ocr/{input,output,archive}
sudo chown -R ocr:ocr /var/ocr /var/log/ocr

# Copy application files
sudo mkdir -p /opt/ocr-processor
sudo cp -r . /opt/ocr-processor/
cd /opt/ocr-processor

# Create virtual environment
python -m venv venv
./venv/bin/pip install -r requirements.txt

# Create systemd service
sudo cp deploy/ocr-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ocr-api
sudo systemctl start ocr-api
```

### SSL/TLS Configuration

For production HTTPS:

```nginx
server {
    listen 443 ssl http2;
    server_name ocr.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/ocr.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ocr.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Administration

### System Monitoring

#### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database health
docker-compose exec postgres pg_isready -U ocr_user -d ocr_db

# Service status
docker-compose ps
```

#### Log Monitoring

```bash
# Real-time logs
docker-compose logs -f ocr-api

# Search for errors
docker-compose logs ocr-api | grep ERROR

# View log files
tail -f /var/log/ocr/ocr_processor.log
```

### Routine Maintenance

#### Daily Tasks

- Verify API health
- Check disk space
- Review error logs

#### Weekly Tasks

- Analyze performance metrics
- Review job success rates
- Clean up old logs
- Verify backup integrity

#### Monthly Tasks

- Capacity planning analysis
- Database maintenance
- Security audit
- Performance optimization

### Backup and Recovery

#### Database Backup

```bash
# Create backup
docker-compose exec postgres pg_dump -U ocr_user ocr_db > backup.sql

# Restore from backup
docker-compose exec -T postgres psql -U ocr_user -d ocr_db < backup.sql
```

#### File Backup

```bash
# Backup output files
tar -czf ocr_files_backup.tar.gz /var/ocr/output/

# Backup with rsync
rsync -avz /var/ocr/output/ backup:/path/to/backup/
```

### Scaling Guidelines

| Load Level                | Workers | CPU | RAM  | Storage |
| ------------------------- | ------- | --- | ---- | ------- |
| Light (<10 files/day)     | 1       | 2   | 4GB  | 50GB    |
| Medium (10-100 files/day) | 2-3     | 4   | 8GB  | 200GB   |
| Heavy (100+ files/day)    | 4+      | 8   | 16GB | 500GB+  |

---

## Troubleshooting

### Common Issues

#### Tesseract Not Found

```bash
# Verify installation
tesseract --version

# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-heb

# macOS
brew install tesseract tesseract-lang
```

#### Permission Errors

```bash
# Check file permissions
ls -la input.pdf

# Fix permissions
chmod 644 input.pdf

# Check directory access
ls -la /path/to/documents/
```

#### High Memory Usage

```bash
# Reduce concurrent jobs
export OCR_MAX_CONCURRENT_JOBS=2

# Monitor memory usage
docker stats
```

#### Database Connection Errors

```bash
# Check database logs
docker-compose logs postgres

# Test connection
docker-compose exec ocr-api python -c "from database_manager import get_database_manager; print('DB OK')"
```

#### OCR Processing Failures

```bash
# Check Tesseract installation
tesseract --version

# Verify file permissions
ls -la /var/ocr/input/

# Check OCR logs
tail -f /var/log/ocr/ocr_errors.log
```

### Performance Tuning

```bash
# CPU optimization
export OCR_MAX_CONCURRENT_JOBS=$(nproc)

# Memory optimization
export OCR_MAX_FILE_SIZE=2147483648

# Parallel processing
export OCR_JOBS=0  # Use all available cores
```

### Getting Help

1. Check logs: `/var/log/ocr/ocr_errors.log`
2. Health check: `curl http://localhost:8000/health`
3. Database status: `docker-compose exec postgres pg_isready`
4. Service status: `docker-compose ps`

---

## Security

### Authentication

#### API Key Generation

```bash
# Generate secure API key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### Setting API Key

```bash
export OCR_API_KEY="your-generated-api-key"
```

### Input Validation

The system validates all inputs:

- Path traversal prevention
- File type verification
- Suspicious pattern detection
- Size limits enforcement

### File Security

- Suspicious files are quarantined
- File permissions are validated
- MIME type detection with magic numbers
- SHA256 checksum calculation

### Security Best Practices

1. **Keep software updated**: Regularly update Tesseract and dependencies
2. **Use HTTPS**: Always use SSL/TLS in production
3. **Limit permissions**: Use least-privilege user accounts
4. **Monitor logs**: Review security logs regularly
5. **Backup data**: Maintain regular backups
6. **Access control**: Restrict API access to authorized users

### Security Headers

```nginx
add_header X-Frame-Options DENY;
add_header X-Content-Type-Options nosniff;
add_header X-XSS-Protection "1; mode=block";
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
```

---

## Contributing

### Reporting Issues

1. Check existing issues first
2. Provide detailed reproduction steps
3. Include logs and error messages
4. Specify environment details

### Pull Requests

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Update documentation
5. Submit pull request

### Code Style

- Follow PEP 8
- Use type hints
- Write docstrings
- Add unit tests
- Update changelog

---

## License

This OCR processing suite is part of the VirtualBox Technologies toolkit and is available for use in document processing workflows.

---

## Support

### Getting Help

1. **Documentation**: Check this guide and README.md
2. **API Docs**: Visit <http://localhost:8000/docs>
3. **Issues**: Create GitHub issue
4. **Email**: Contact support team

### Emergency Contacts

- **Primary Administrator**: <admin@yourcompany.com>
- **Development Team**: <dev-team@yourcompany.com>
- **On-call Support**: +1-234-567-8900

---

## Changelog

### Version 2.0.0

- New REST API with FastAPI
- Database integration for job tracking
- Multi-channel notifications
- Enhanced security validation
- Structured logging with structlog
- Progress tracking and metrics
- Docker Compose deployment
- GUI application

### Version 1.x

- Initial CLI tools
- Basic OCR processing
- Multiple processing modes
- Multi-language support

---

_Last updated: 2024-01-15_
_Documentation version: 2.0.0_
