# ERPX AI Accounting - Dockerfile
# ================================
# Production-ready container with DO Agent qwen3-32b support
# NO LOCAL LLM - All inference through DO Agent API

FROM python:3.10-slim

# Build arguments for version tracking
ARG GIT_SHA=unknown
ARG BUILD_TIME=unknown
ARG VERSION=unknown

# Set version info as environment variables
ENV GIT_SHA=${GIT_SHA}
ENV BUILD_TIME=${BUILD_TIME}
ENV VERSION=${VERSION}

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/root/erp-ai
ENV TZ=Asia/Ho_Chi_Minh

# IMPORTANT: Disable local LLM
ENV DISABLE_LOCAL_LLM=1
ENV LLM_PROVIDER=do_agent

# Set work directory
WORKDIR /root/erp-ai

# Install system dependencies for OCR and PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install additional dependencies for production
RUN pip install --no-cache-dir \
    uvicorn[standard] \
    gunicorn \
    httpx \
    tenacity \
    pdfplumber \
    pandas \
    openpyxl \
    python-telegram-bot \
    langgraph \
    temporalio \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp \
    PyJWT

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /root/erp-ai/data/uploads \
    /root/erp-ai/data/kb \
    /root/erp-ai/logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command - API server
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
