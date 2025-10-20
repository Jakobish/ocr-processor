# 👨‍💼 OCR Processor Enterprise - Administration Guide

## Overview

This guide provides comprehensive instructions for administering and maintaining the OCR Processor Enterprise Edition in production environments.

## 📊 System Monitoring

### Dashboard Access

**Web Interface:**
- **URL:** `http://your-server:8000/docs` (API documentation)
- **Health Check:** `http://your-server:8000/health`
- **Metrics:** `http://your-server:8000/metrics`

**Database Interface:**
- **PgAdmin:** `http://your-server:5050` (if deployed)
- **Direct Access:** `psql -h localhost -U ocr_user -d ocr_db`

### Key Metrics to Monitor

#### Application Metrics
```bash
# Get current metrics via API
curl http://localhost:8000/metrics

# Monitor job queue
curl http://localhost:8000/status
```

#### System Metrics
```bash
# CPU and Memory usage
docker stats

# Disk usage
df -h /var/ocr/

# Network connections
ss -tuln | grep :8000
```

### Log Monitoring

#### Application Logs
```bash
# Real-time log monitoring
docker-compose logs -f ocr-api
docker-compose logs -f ocr-worker

# Search for errors
docker-compose logs ocr-api | grep ERROR
docker-compose logs ocr-worker | grep -i "failed\|error"
```

#### System Logs
```bash
# Service logs
journalctl -u ocr-api -f
journalctl -u ocr-worker -f

# Nginx logs (if used)
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

## 🔧 Routine Maintenance

### Daily Tasks

#### 1. Health Verification
```bash
#!/bin/bash
# daily_health_check.sh

echo "=== OCR Processor Daily Health Check ==="
echo "Timestamp: $(date)"

# API Health
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API Server: Healthy"
else
    echo "❌ API Server: Unhealthy"
fi

# Database Health
if docker-compose exec postgres pg_isready -U ocr_user -d ocr_db > /dev/null 2>&1; then
    echo "✅ Database: Connected"
else
    echo "❌ Database: Connection Failed"
fi

# Worker Status
if pgrep -f "python.*ocr_combined" > /dev/null; then
    echo "✅ OCR Worker: Running"
else
    echo "❌ OCR Worker: Not Running"
fi

# Disk Space
DISK_USAGE=$(df /var/ocr | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo "✅ Disk Usage: ${DISK_USAGE}%"
else
    echo "⚠️ Disk Usage: ${DISK_USAGE}% (High)"
fi

echo "=== End of Health Check ==="
```

#### 2. Log Rotation
```bash
# Manual log rotation
docker-compose exec ocr-api python -c "
from logger import log_manager
log_manager.cleanup_old_logs(7)  # Keep 7 days
print('Logs cleaned up')
"

# Database log cleanup
docker-compose exec postgres psql -U ocr_user -d ocr_db -c "
SELECT cleanup_old_records(30);  -- Keep 30 days
"
```

### Weekly Tasks

#### 1. Performance Analysis
```bash
# Generate performance report
curl "http://localhost:8000/metrics?days=7" > weekly_report.json

# Database statistics
docker-compose exec postgres psql -U ocr_user -d ocr_db -c "
SELECT
    COUNT(*) as total_jobs,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_jobs,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_jobs,
    AVG(processing_time) as avg_processing_time
FROM ocr_jobs
WHERE created_at >= NOW() - INTERVAL '7 days';
"
```

#### 2. Security Audit
```bash
# Check file permissions
find /var/ocr -type f -exec ls -la {} \; | grep -v "ocr.ocr"

# Check for suspicious files in quarantine
ls -la /app/quarantine/

# Review authentication logs
grep "authentication\|login\|api" /var/log/ocr/ocr_processor.log
```

#### 3. Backup Verification
```bash
# Test database backup restoration
pg_restore --schema-only --dry-run ocr_backup_$(date +%Y%m%d).sql

# Verify file backup integrity
tar -tzf ocr_files_backup.tar.gz | head -10
```

### Monthly Tasks

#### 1. Capacity Planning
```bash
# Analyze storage growth
du -sh /var/ocr/output/ /var/ocr/archive/ /var/log/ocr/

# Database size analysis
docker-compose exec postgres psql -U ocr_user -d ocr_db -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

#### 2. Performance Optimization
```bash
# Update Tesseract if needed
tesseract --version

# Optimize PostgreSQL settings
docker-compose exec postgres psql -U ocr_user -d ocr_db -c "
-- Check for slow queries
SELECT * FROM pg_stat_statements
ORDER BY mean_time DESC LIMIT 10;
"
```

## 🚨 Incident Response

### Service Outage

#### 1. Immediate Actions
```bash
# Check service status
docker-compose ps

# View recent logs
docker-compose logs --tail=50 ocr-api
docker-compose logs --tail=50 ocr-worker

# Check system resources
top -n 1 | head -20
df -h
```

#### 2. Recovery Procedures

**API Server Down:**
```bash
# Restart API server
docker-compose restart ocr-api

# Check if port is in use
netstat -tuln | grep :8000

# Manual start if needed
python -m uvicorn api_server:get_api_server(config).app --host 0.0.0.0 --port 8000
```

**Worker Process Down:**
```bash
# Check for stuck processes
ps aux | grep ocr_combined

# Kill stuck processes
pkill -f "python.*ocr_combined"

# Restart worker
docker-compose restart ocr-worker

# Or start manually
python ocr_combined.py --mode force /path/to/input &
```

**Database Connection Issues:**
```bash
# Check PostgreSQL status
docker-compose logs postgres

# Restart database
docker-compose restart postgres

# Check connection
docker-compose exec postgres pg_isready -U ocr_user -d ocr_db
```

### Data Issues

#### File Corruption
```bash
# Identify corrupted files
find /var/ocr/input -name "*.pdf" -exec sh -c '
    if ! file "$1" | grep -q PDF; then
        echo "Corrupted: $1"
    fi
' _ {} \;

# Move corrupted files
mkdir -p /var/ocr/quarantine
find /var/ocr/input -name "*.pdf" -exec sh -c '
    if ! file "$1" | grep -q PDF; then
        mv "$1" /var/ocr/quarantine/
    fi
' _ {} \;
```

#### Database Corruption
```bash
# Check database integrity
docker-compose exec postgres psql -U ocr_user -d ocr_db -c "
SELECT schemaname, tablename, attname, n_distinct, most_common_vals
FROM pg_stats
WHERE schemaname = 'public';
"

# Repair if needed
docker-compose exec postgres vacuumdb -U ocr_user -d ocr_db --analyze
```

## ⚙️ Configuration Management

### Environment Variables

#### Production Settings
```bash
# Performance tuning
export OCR_MAX_CONCURRENT_JOBS=8
export OCR_TIMEOUT_PER_FILE=600
export OCR_MAX_FILE_SIZE=2147483648

# Logging
export OCR_LOG_LEVEL=WARNING
export OCR_LOG_TO_FILE=true
export OCR_REMOTE_LOG_URL=https://logs.yourcompany.com/webhook

# Notifications
export OCR_NOTIFICATION_EMAIL=ops@yourcompany.com
export OCR_WEBHOOK_URL=https://monitoring.yourcompany.com/webhooks/ocr
```

#### Development Settings
```bash
# Development configuration
export OCR_LOG_LEVEL=DEBUG
export OCR_MAX_CONCURRENT_JOBS=2
export OCR_TIMEOUT_PER_FILE=60
export OCR_ENABLE_API=true
export OCR_API_PORT=8000
```

### Configuration Updates

#### Via Configuration File
```bash
# Edit configuration
nano ocr_config.json

# Validate configuration
python -c "
from config import OCRConfig
try:
    config = OCRConfig()
    print('✅ Configuration is valid')
except Exception as e:
    print(f'❌ Configuration error: {e}')
"

# Restart services to apply changes
docker-compose restart
```

#### Via Environment Variables
```bash
# Set permanent environment variables
echo 'export OCR_MAX_CONCURRENT_JOBS=4' >> ~/.bashrc
source ~/.bashrc

# Apply immediately
export OCR_MAX_CONCURRENT_JOBS=4
docker-compose restart ocr-worker
```

## 🔒 Security Management

### Access Control

#### API Security
```bash
# Generate secure API key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set API key
export OCR_API_KEY="your-generated-api-key"

# Test API key
curl -H "Authorization: Bearer your-api-key" http://localhost:8000/health
```

#### File System Security
```bash
# Set proper ownership
sudo chown -R ocr:ocr /var/ocr/

# Set restrictive permissions
sudo chmod -R 750 /var/ocr/input/
sudo chmod -R 755 /var/ocr/output/
sudo chmod -R 700 /var/ocr/quarantine/

# Enable audit logging
sudo auditctl -w /var/ocr/ -p rwxa -k ocr_access
```

### SSL/TLS Management

#### Certificate Renewal
```bash
# Check certificate expiry
sudo certbot certificates

# Renew certificates
sudo certbot renew --dry-run  # Test first
sudo certbot renew

# Reload Nginx
sudo nginx -t && sudo nginx -s reload
```

#### Security Headers
```nginx
# Add to Nginx configuration
add_header X-Frame-Options DENY;
add_header X-Content-Type-Options nosniff;
add_header X-XSS-Protection "1; mode=block";
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
```

## 📈 Performance Optimization

### Memory Management

#### Monitoring Memory Usage
```bash
# Real-time memory monitoring
watch -n 5 'docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"'

# Memory usage by process
ps aux --sort=-%mem | head -10

# Identify memory leaks
valgrind --tool=massif python ocr_combined.py --mode cli test.pdf
```

#### Memory Optimization
```bash
# Reduce worker memory usage
export OCR_MAX_CONCURRENT_JOBS=2

# Process large files in chunks
export OCR_CHUNK_SIZE=5

# Enable garbage collection
export PYTHONOPTIMIZE=1
```

### CPU Optimization

#### Load Balancing
```bash
# Distribute load across workers
docker-compose up -d --scale ocr-worker=4

# Monitor CPU usage
mpstat -P ALL 1 5

# Adjust worker priorities
renice -n 10 $(pgrep -f "python.*ocr_combined")
```

#### Processing Optimization
```bash
# Use appropriate OCR settings for file types
export OCR_TESSERACT_CONFIG="--psm 3 --oem 3"

# Enable parallel processing
export OCR_JOBS=0  # Use all available cores

# Optimize for specific languages
export OCR_DEFAULT_LANGUAGE="heb+eng"
```

### Storage Optimization

#### Disk Space Management
```bash
# Monitor disk usage
watch -n 60 'df -h /var/ocr/'

# Clean old output files
find /var/ocr/output/ -type d -mtime +30 -exec rm -rf {} \; 2>/dev/null

# Archive old files
tar -czf /backup/ocr_$(date +%Y%m%d).tar.gz /var/ocr/output/
```

#### I/O Optimization
```bash
# Use faster storage for temporary files
export OCR_TEMP_DIR="/tmp/ocr"

# Enable compression for large files
export OCR_COMPRESS_OUTPUT=true

# Use SSD for active processing
mount -t tmpfs -o size=2G tmpfs /tmp/ocr/
```

## 🔧 Advanced Administration

### Database Administration

#### Query Optimization
```sql
-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM ocr_jobs WHERE status = 'completed';

-- Create performance indexes
CREATE INDEX CONCURRENTLY idx_ocr_jobs_performance
ON ocr_jobs(status, created_at DESC, processing_time);

-- Update table statistics
ANALYZE ocr_jobs;
ANALYZE ocr_files;
ANALYZE ocr_audit_logs;
```

#### Backup and Recovery
```bash
# Create backup
docker-compose exec postgres pg_dump -U ocr_user ocr_db > backup.sql

# Restore from backup
docker-compose exec -T postgres psql -U ocr_user -d ocr_db < backup.sql

# Point-in-time recovery (if WAL archiving is enabled)
docker-compose exec postgres psql -U ocr_user -d ocr_db -c "
SELECT pg_wal_replay_resume();
"
```

### Service Scaling

#### Horizontal Scaling
```bash
# Scale API servers
docker-compose up -d --scale ocr-api=2

# Scale workers based on load
docker-compose up -d --scale ocr-worker=6

# Use load balancer
# Configure Nginx to distribute requests across API instances
```

#### Auto-scaling (with Kubernetes)
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ocr-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ocr-worker
  template:
    metadata:
      labels:
        app: ocr-worker
    spec:
      containers:
      - name: worker
        image: ocr-processor:2.0.0
        command: ["worker"]
        resources:
          requests:
            memory: "2Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "1000m"
```

### Integration Management

#### Webhook Configuration
```bash
# Test webhook connectivity
curl -X POST $OCR_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"test": true, "timestamp": "'$(date -Iseconds)'"}'

# Monitor webhook responses
tail -f /var/log/ocr/ocr_processor.log | grep webhook
```

#### Email Notifications
```bash
# Test email configuration
python -c "
from notification_manager import get_notification_manager
from config import config
nm = get_notification_manager(config)
test_msg = type('TestMsg', (), {
    'subject': 'OCR Test Email',
    'body': 'This is a test email from OCR Processor',
    'message_type': 'info',
    'priority': 'normal',
    'metadata': {}
})()
print('Email test:', nm.send_notification(test_msg))
"
```

## 📋 Troubleshooting Scripts

### System Health Script
```bash
#!/bin/bash
# ocr_health_check.sh

echo "=== OCR Processor Health Check ==="
echo "Date: $(date)"

# Check services
services=("ocr-api" "ocr-worker" "postgres" "redis")
for service in "${services[@]}"; do
    if docker-compose ps $service | grep -q "Up"; then
        echo "✅ $service: Running"
    else
        echo "❌ $service: Down"
    fi
done

# Check resources
echo -e "\n=== Resource Usage ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Check recent errors
echo -e "\n=== Recent Errors ==="
docker-compose logs --tail=10 ocr-api | grep -i error || echo "No recent errors in API"
docker-compose logs --tail=10 ocr-worker | grep -i error || echo "No recent errors in worker"

echo -e "\n=== Health Check Complete ==="
```

### Performance Analysis Script
```bash
#!/bin/bash
# ocr_performance_analysis.sh

echo "=== OCR Performance Analysis ==="

# Get metrics from API
METRICS=$(curl -s http://localhost:8000/metrics)

# Database statistics
DB_STATS=$(docker-compose exec postgres psql -U ocr_user -d ocr_db -t -c "
SELECT
    COUNT(*) as total_jobs,
    AVG(processing_time) as avg_time,
    SUM(processed_files) as total_processed
FROM ocr_jobs
WHERE created_at >= NOW() - INTERVAL '24 hours';
")

echo "API Metrics: $METRICS"
echo "Database Stats: $DB_STATS"

# System performance
echo -e "\n=== System Performance ==="
vmstat 1 5
iostat -x 1 5
```

## 📞 Emergency Procedures

### Complete System Recovery

#### 1. Immediate Actions
```bash
# Stop all services
docker-compose down

# Check system resources
df -h
free -h
top -n 1 | head -10

# Check for stuck processes
ps aux | grep -E "(ocr|python)" | grep -v grep
```

#### 2. Data Preservation
```bash
# Backup current state
cp -r /var/ocr/ /backup/ocr_emergency_$(date +%Y%m%d_%H%M%S)/

# Database backup
docker-compose exec postgres pg_dump -U ocr_user ocr_db > /backup/db_emergency.sql
```

#### 3. Service Restoration
```bash
# Start database first
docker-compose up -d postgres

# Wait for database readiness
sleep 30

# Start API
docker-compose up -d ocr-api

# Start workers
docker-compose up -d ocr-worker

# Verify restoration
curl http://localhost:8000/health
```

### Contact Information

#### Emergency Contacts
- **Primary Administrator:** admin@yourcompany.com | +1-234-567-8900
- **Backup Administrator:** backup-admin@yourcompany.com | +1-234-567-8901
- **Development Team:** dev-team@yourcompany.com | +1-234-567-8902
- **Infrastructure Team:** infra@yourcompany.com | +1-234-567-8903

#### Escalation Procedure
1. **Level 1:** Try self-service recovery procedures
2. **Level 2:** Contact primary administrator
3. **Level 3:** Contact development team
4. **Level 4:** Contact infrastructure team

---

**For urgent issues, please contact the emergency support team immediately.**