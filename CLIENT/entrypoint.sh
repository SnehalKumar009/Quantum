#!/bin/sh
# entrypoint.sh - boot-time qConnect KME probe (Proof 3), then exec CMD.
set -e

echo "[entrypoint] ======== qConnect KME boot probe (Proof 3) ========"
if [ -x /usr/local/bin/qkd-status ] && [ -n "${QKD_KME_URL:-}" ]; then
    /usr/local/bin/qkd-status || true
else
    echo "[entrypoint] qkd-status not runnable or QKD_KME_URL unset; skipping"
fi
echo "[entrypoint] ======== handing off to: $* ========"

exec "$@"

