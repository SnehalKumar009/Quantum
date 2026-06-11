#!/bin/sh
# entrypoint.sh - generate a self-signed TLS cert on first run, then exec CMD.
set -e

CERT_DIR="${CERT_DIR:-/app/certs}"
CERT_FILE="${CERT_DIR}/server.crt"
KEY_FILE="${CERT_DIR}/server.key"
CERT_CN="${CERT_CN:-server01}"

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "[entrypoint] No TLS cert found, generating self-signed cert for CN=${CERT_CN}..."
    openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
        -keyout "$KEY_FILE" -out "$CERT_FILE" \
        -subj "/CN=${CERT_CN}" \
        -addext "subjectAltName=DNS:${CERT_CN},DNS:localhost,IP:127.0.0.1" \
        >/dev/null 2>&1
    echo "[entrypoint] Generated $CERT_FILE"
else
    echo "[entrypoint] Reusing existing TLS cert at $CERT_FILE"
fi

exec "$@"

