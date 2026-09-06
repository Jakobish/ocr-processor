FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-heb tesseract-ocr-eng ghostscript qpdf \
    libmagic1 poppler-utils unpaper python3-tk curl fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 ocr && useradd --uid 10001 --gid ocr --create-home ocr
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
COPY cli/ cli/
COPY alembic.ini .
COPY migrations/ migrations/
RUN mkdir -p /app/data /app/logs /app/output /app/temp /app/quarantine \
    && chown -R ocr:ocr /app && chmod 700 /app/data
USER ocr
EXPOSE 8000
CMD ["uvicorn", "enterprise.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
