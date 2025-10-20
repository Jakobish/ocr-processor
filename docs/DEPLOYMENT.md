# 🚀 OCR Processor Enterprise - Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the OCR Processor Enterprise Edition in various environments, from development to production.

## 📋 Prerequisites

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+, CentOS 8+, RHEL 8+) or macOS 12+
- **RAM**: 4GB minimum, 8GB recommended for production
- **Storage**: 10GB free space minimum, SSD recommended
- **CPU**: 2 cores minimum, 4+ cores recommended for high throughput

### Software Dependencies
- **Docker**: 20.10.0+ (for containerized deployment)
- **Docker Compose**: 2.0+ (for multi-service deployment)
- **Python**: 3.11+ (for manual installation)
- **Tesseract OCR**: 5.0+
- **PostgreSQL**: 13+ (for database features)

## 🐳 Docker Deployment (Recommended)

### Quick Start

1. **Clone and navigate to the project:**
   ```bash
   git clone <repository-url>
   cd ocr-processor
   ```

2. **Start all services:**
   ```bash
   docker-compose up -d
   ```

3. **Verify deployment:**
   ```bash
   # Check service status
   docker-compose ps

   # View logs
   docker-compose logs -f ocr-api

   # Health check
   curl http://localhost:8000/health
   ```

### Production Deployment

1. **Create environment file:**
   ```bash
   cp .env.example .env
   # Edit .env with your production values
   ```

2. **Configure SSL (optional):**
   ```bash
   # Place SSL certificates in docker/ssl/
   # Update nginx.conf accordingly
   ```

3. **Scale services:**
   ```bash
   # Scale workers based on load
   docker-compose up -d --scale ocr-worker=3
   ```

4. **Update and restart:**
   ```bash
   # Pull latest images and restart
   docker-compose pull
   docker-compose up -d --force-recreate
   ```

### Docker Service Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │     OCR API     │    │  OCR Workers    │
│   (Nginx)       │◄──►│   (FastAPI)     │◄──►│  (Batch Jobs)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │      Redis      │    │    Filebeat     │
│   (Database)    │    │   (Cache/Q)     │    │  (Log Ship)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 Manual Installation

### 1. System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-heb \
    qpdf \
    poppler-utils \
    postgresql-13 \
    postgresql-contrib \
    redis-server \
    nginx
```

**CentOS/RHEL:**
```bash
sudo yum install -y \
    tesseract \
    qpdf \
    poppler-utils \
    postgresql-server \
    postgresql-contrib \
    redis \
    nginx
```

### 2. Python Environment

```bash
# Create virtual environment
python -m venv ocr-env
source ocr-env/bin/activate  # On Windows: ocr-env\Scripts\activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Database Setup

```bash
# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql
```

```sql
CREATE DATABASE ocr_db;
CREATE USER ocr_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE ocr_db TO ocr_user;
ALTER USER ocr_user CREATEDB;
\q
```

### 4. Application Configuration

```bash
# Copy and edit configuration
cp ocr_config.json.example ocr_config.json
# Edit ocr_config.json with your settings

# Set environment variables
export OCR_DATABASE_URL="postgresql://ocr_user:password@localhost/ocr_db"
export OCR_NOTIFICATION_EMAIL="admin@yourcompany.com"
export OCR_SMTP_SERVER="smtp.yourcompany.com"
# ... other variables
```

### 5. Start Services

```bash
# Start Redis
sudo systemctl start redis-server

# Start API server
python -m uvicorn api_server:get_api_server(config).app --host 0.0.0.0 --port 8000 &

# Start worker processes
python ocr_combined.py --mode force /path/to/documents &
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OCR_LOG_LEVEL` | Logging level | INFO | No |
| `OCR_DATABASE_URL` | Database connection | - | Yes* |
| `OCR_NOTIFICATION_EMAIL` | Admin email | - | No |
| `OCR_SMTP_SERVER` | SMTP server | - | No |
| `OCR_WEBHOOK_URL` | Webhook URL | - | No |
| `OCR_MAX_CONCURRENT_JOBS` | Max parallel jobs | 4 | No |
| `OCR_MAX_FILE_SIZE` | Max file size (bytes) | 104857600 | No |

*Required for database features

### Configuration File

Create `ocr_config.json`:

```json
{
  "default_language": "heb+eng",
  "default_mode": "cli",
  "max_concurrent_jobs": 4,
  "archive_originals": true,
  "enable_database": true,
  "database_url": "postgresql://user:pass@localhost/ocr_db",
  "enable_notifications": true,
  "notification_email": "admin@example.com",
  "smtp_server": "smtp.example.com",
  "smtp_port": 587,
  "smtp_username": "user@example.com",
  "smtp_password": "secure_password",
  "webhook_url": "https://your-system.com/webhooks/ocr",
  "enable_api": true,
  "api_port": 8000,
  "log_level": "INFO",
  "log_to_file": true,
  "log_directory": "/var/log/ocr"
}
```

## 🔒 Security Configuration

### API Authentication

1. **Set secure API key:**
   ```bash
   export OCR_API_KEY="your-secure-api-key-here"
   ```

2. **Configure CORS:**
   ```json
   {
     "api_cors_origins": [
       "https://yourdomain.com",
       "https://app.yourdomain.com"
     ]
   }
   ```

### File Permissions

```bash
# Set proper permissions
sudo mkdir -p /var/log/ocr /var/ocr/{input,output,archive}
sudo chown -R ocr:ocr /var/log/ocr /var/ocr/
sudo chmod -R 750 /var/log/ocr /var/ocr/

# Add user to OCR group if needed
sudo usermod -a -G ocr $USER
```

### SSL/TLS Configuration

For production HTTPS:

1. **Get SSL certificate:**
   ```bash
   # Using Let's Encrypt
   sudo certbot certonly --nginx -d ocr.yourdomain.com
   ```

2. **Configure Nginx:**
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
       }
   }
   ```

## 📊 Monitoring and Maintenance

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database connectivity
docker-compose exec postgres pg_isready -U ocr_user -d ocr_db

# Service status
docker-compose ps
```

### Log Management

```bash
# View application logs
docker-compose logs -f ocr-api
docker-compose logs -f ocr-worker

# View system logs
journalctl -u ocr-api -f
tail -f /var/log/ocr/ocr_processor.log

# Log rotation
docker-compose exec ocr-api python -c "from logger import log_manager; log_manager.cleanup_old_logs(30)"
```

### Database Maintenance

```bash
# Connect to database
docker-compose exec postgres psql -U ocr_user -d ocr_db

# Cleanup old records (older than 90 days)
SELECT cleanup_old_records(90);

# View job statistics
SELECT * FROM job_summary ORDER BY created_at DESC LIMIT 10;

# Monitor performance
SELECT * FROM recent_activity WHERE activity_type = 'job' ORDER BY timestamp DESC;
```

### Backup and Recovery

```bash
# Database backup
docker-compose exec postgres pg_dump -U ocr_user ocr_db > ocr_backup_$(date +%Y%m%d).sql

# File backup
tar -czf ocr_files_$(date +%Y%m%d).tar.gz /var/ocr/output/

# Restore database
docker-compose exec -T postgres psql -U ocr_user -d ocr_db < ocr_backup.sql
```

## 🚨 Troubleshooting

### Common Issues

**High memory usage:**
```bash
# Reduce concurrent jobs
export OCR_MAX_CONCURRENT_JOBS=2

# Monitor memory usage
docker stats
```

**Database connection errors:**
```bash
# Check database logs
docker-compose logs postgres

# Test connection
docker-compose exec ocr-api python -c "from database_manager import get_database_manager; print('DB OK')"
```

**OCR processing failures:**
```bash
# Check Tesseract installation
tesseract --version

# Verify file permissions
ls -la /var/ocr/input/

# Check OCR logs for details
tail -f /var/log/ocr/ocr_errors.log
```

**API timeouts:**
```bash
# Increase timeout settings
export OCR_TIMEOUT_PER_FILE=600

# Check worker logs
docker-compose logs ocr-worker
```

### Performance Tuning

```bash
# CPU optimization
export OCR_MAX_CONCURRENT_JOBS=$(nproc)

# Memory optimization for large files
export OCR_MAX_FILE_SIZE=2147483648  # 2GB

# Enable progress bars only for CLI
export OCR_PROGRESS_BAR=false
```

### Scaling Guidelines

| Load Level | Workers | CPU | RAM | Storage |
|------------|---------|-----|-----|---------|
| Light (<10 files/day) | 1 | 2 | 4GB | 50GB |
| Medium (10-100 files/day) | 2-3 | 4 | 8GB | 200GB |
| Heavy (100+ files/day) | 4+ | 8 | 16GB | 500GB+ |

## 🔄 Upgrading

### Docker Upgrade

```bash
# Stop services
docker-compose down

# Pull latest images
docker-compose pull

# Update database schema (if needed)
docker-compose run --rm ocr-api python -c "from database_manager import DatabaseManager; dm = DatabaseManager(config); dm.migrate_database()"

# Restart services
docker-compose up -d
```

### Manual Upgrade

```bash
# Backup database
cp ocr_config.json ocr_config.json.backup
docker-compose exec postgres pg_dump -U ocr_user ocr_db > backup.sql

# Update code
git pull
pip install -r requirements.txt --upgrade

# Run migrations
python -c "from database_manager import DatabaseManager; dm = DatabaseManager(config); dm.migrate_database()"

# Restart services
sudo systemctl restart ocr-api ocr-worker
```

## 📞 Support

### Getting Help

1. **Check logs:** `/var/log/ocr/ocr_errors.log`
2. **Health check:** `curl http://localhost:8000/health`
3. **Database status:** `docker-compose exec postgres pg_isready`
4. **Service status:** `docker-compose ps`

### Emergency Contacts

- **System Administrator:** admin@yourcompany.com
- **Development Team:** dev-team@yourcompany.com
- **On-call Support:** +1-234-567-8900

---

**For additional support, please contact the OCR Processor team or create an issue in the project repository.**