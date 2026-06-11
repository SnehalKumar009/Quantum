# =============================================================================
# qconnect - simulated RNG / key-distribution service for the lab.
# =============================================================================
FROM python:3.12-slim

LABEL project="quantum-secure-lab" \
      component="qconnect" \
      description="HTTP API that generates and serves key-id/key pairs"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    QCONNECT_DATA_DIR=/data/keys

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/

RUN useradd --create-home --shell /bin/bash appuser \
 && mkdir -p ${QCONNECT_DATA_DIR} \
 && chown -R appuser:appuser /app ${QCONNECT_DATA_DIR}
USER appuser

EXPOSE 9000/tcp

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]

