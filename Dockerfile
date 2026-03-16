# ==============================================================================
# Photo Metadata Extractor — Docker image with OpenVINO NPU support
# ==============================================================================
# Multi-stage build:
#   1. Builder: install Python deps
#   2. Runtime: minimal image with OpenVINO + NPU drivers
# ==============================================================================

# --- Stage 1: Builder --------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install .

# --- Stage 2: Runtime --------------------------------------------------------
FROM python:3.12-slim AS runtime

# Install runtime system deps:
#   - libgl1 + libglib2: OpenCV headless
#   - Intel NPU/GPU compute drivers (if available in repos)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
WORKDIR /app
COPY src/ src/

# Model cache directory (persisted via volume)
RUN mkdir -p /app/models

# Default: scan /data, output CSV to /data/photo_metadata.csv
ENV PME_ROOT_DIR=/data \
    PME_MODEL_CACHE_DIR=/app/models \
    PME_EXECUTION_PROVIDER=auto \
    PME_NPU_DEVICE=NPU

# Health check: ensure Python and deps load
HEALTHCHECK --interval=30s --timeout=5s \
    CMD python -c "import src.main" || exit 1

ENTRYPOINT ["python", "-m", "src.main"]
