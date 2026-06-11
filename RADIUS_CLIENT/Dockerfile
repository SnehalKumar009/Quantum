# =============================================================================
# radius-client - the NAS that sits between supplicants and the RADIUS server.
# =============================================================================
FROM python:3.12-slim

LABEL project="quantum-secure-lab" \
      component="radius-client" \
      description="NAS: accepts HTTP /auth, forwards as RADIUS Access-Request"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/

RUN useradd --create-home --shell /bin/bash appuser \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 8082/tcp

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8082"]

