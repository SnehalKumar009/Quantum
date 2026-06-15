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

# System deps (kept minimal). curl + jq used by the qkd-status probe.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates jq \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application source
COPY app/ ./app/

# Real qConnect (ETSI 014) status probe + entrypoint wrapper that runs it
# at boot (Proof 3 of SAE registration), then exec's the original CMD.
COPY scripts/qkd-status.sh /usr/local/bin/qkd-status
COPY entrypoint.sh         /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/qkd-status /usr/local/bin/entrypoint.sh \
 && chmod +x /usr/local/bin/qkd-status /usr/local/bin/entrypoint.sh

# Drop privileges
RUN useradd --create-home --shell /bin/bash appuser \
 && chown -R appuser:appuser /app
USER appuser

# Default entry point - probe qConnect, then run the client workflow once.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "-m", "app.main"]

