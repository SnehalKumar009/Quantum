# =============================================================================
# server01 - Python application server for the Quantum Secure Lab
# =============================================================================
FROM python:3.12-slim

LABEL project="quantum-secure-lab" \
      component="server01" \
      description="App server: RADIUS auth -> TLS listener -> quantum key -> encrypted msgs"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates openssl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
# Strip any CRLF that Windows editors / git autocrlf may have introduced,
# otherwise the shebang fails inside the Linux container.
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh \
 && chmod +x /usr/local/bin/entrypoint.sh \
 && mkdir -p /app/certs

RUN useradd --create-home --shell /bin/bash appuser \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 8443/tcp

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "-m", "app.main"]

