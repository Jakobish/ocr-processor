# OCR Processor Enterprise Dockerfile
# Multi-stage build for optimal image size and security

# Stage 1: Builder stage
FROM python:3.11-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-heb \
    libleptonica-dev \
    libtesseract-dev \
    qpdf \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.11-slim as runtime

# Create non-root user for security
RUN groupadd -r ocruser && useradd -r -g ocruser ocruser

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-heb \
    qpdf \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create necessary directories
RUN mkdir -p /app /app/data /app/output /app/logs /app/temp /app/quarantine && \
    chown -R ocruser:ocruser /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/ocruser/.local

# Set environment variables
ENV PATH=/home/ocruser/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Create startup script
RUN echo '#!/bin/bash\n\
if [ "$1" = "api" ]; then\n\
    echo "Starting OCR API Server..."\n\
    python -m uvicorn api_server:get_api_server"(config)".app --host 0.0.0.0 --port 8000\n\
elif [ "$1" = "worker" ]; then\n\
    echo "Starting OCR Worker..."\n\
    python ocr_combined.py "$@"\n\
elif [ "$1" = "gui" ]; then\n\
    echo "Starting OCR GUI..."\n\
    python pdf_ocr_gui.py\n\
else\n\
    echo "Usage: docker run ocr-processor [api|worker|gui] [args...]"\n\
    echo "  api    - Start REST API server"\n\
    echo "  worker - Start OCR processing worker"\n\
    echo "  gui    - Start graphical user interface"\n\
    exec "$@"\n\
fi' > /app/start.sh && chmod +x /app/start.sh

# Health check
RUN echo '#!/bin/bash\n\
if [ "$1" = "api" ]; then\n\
    curl -f http://localhost:8000/health || exit 1\n\
else\n\
    # Check if OCR tools are available\n\
    tesseract --version >/dev/null 2>&1 || exit 1\n\
    ocrmypdf --version >/dev/null 2>&1 || exit 1\n\
fi\n\
echo "healthy"' > /app/healthcheck.sh && chmod +x /app/healthcheck.sh

# Change ownership to non-root user
RUN chown -R ocruser:ocruser /app

# Switch to non-root user
USER ocruser

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /app/healthcheck.sh api || exit 1

# Default command
ENTRYPOINT ["/app/start.sh"]

# Labels for metadata
LABEL maintainer="OCR Processor Team"
LABEL version="2.0.0"
LABEL description="Enterprise OCR Processing Suite with API, GUI, and CLI interfaces"
LABEL org.opencontainers.image.source="https://github.com/ocr-processor/enterprise"

# Runtime configuration
ENV OCR_LOG_LEVEL=INFO
ENV OCR_OUTPUT_BASE_DIR=/app/output
ENV OCR_LOG_DIRECTORY=/app/logs
ENV OCR_MAX_CONCURRENT_JOBS=2
ENV OCR_MAX_FILE_SIZE=104857600
ENV OCR_ENABLE_API=true
ENV OCR_API_HOST=0.0.0.0
ENV OCR_API_PORT=8000