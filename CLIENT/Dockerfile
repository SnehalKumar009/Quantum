# =============================================================================
# client01 - Python application client for the Quantum Secure Lab
# =============================================================================
FROM python:3.12-slim

LABEL project="quantum-secure-lab" \
      component="client01" \
      description="App client: RADIUS auth -> TLS -> quantum key -> encrypted msgs"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps (kept minimal). curl is handy for debugging from inside the container.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application source
COPY app/ ./app/

# Drop privileges
RUN useradd --create-home --shell /bin/bash appuser \
 && chown -R appuser:appuser /app
USER appuser

# Default entry point - runs the client workflow once and exits.
CMD ["python", "-m", "app.main"]

