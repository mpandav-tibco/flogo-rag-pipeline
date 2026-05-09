# Dockerfile.docling — Docling PDF parsing API
# Serves: POST /general/v0/general (multipart PDF → chunked text)
#         GET  /healthcheck
#
# Build:  docker build -f Dockerfile.docling -t docling-api .
# Run:    docker run -p 8001:8001 docling-api

FROM python:3.12-slim

# System deps for Docling's PDF pipeline + EasyOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Docling — pinned to match the locally validated version (2.92.0)
# Install CPU-only torch+torchvision first to avoid pulling ~1.5GB of CUDA packages
# (Docling/sentence-transformers only needs CPU inference)
RUN pip install --no-cache-dir \
    "torch>=2.0,<3.0" \
    "torchvision" \
    --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir \
    "docling==2.92.0" \
    "easyocr>=1.7,<2.0" \
    "sentence-transformers>=2.7,<4.0"

# Pre-download HybridChunker's sentence-transformer model at build time
# so containers start instantly (no cold-download on first request)
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); print('Model cached.')"

# Copy the API server
COPY docling-local-api.py .

EXPOSE 8001

# Healthcheck so docker compose / k8s knows when the service is ready
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/healthcheck')" || exit 1

CMD ["python3", "docling-local-api.py", "--host", "0.0.0.0", "--port", "8001"]
