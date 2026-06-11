#!/bin/sh
# qconnect-fetch - ask QConnect for a fresh key and append it to the
# RADIUS `keys` file in the same format used by `authorize`.
#
# Usage (inside the radius01 container):
#   qconnect-fetch                       # generate new key, store it
#   qconnect-fetch <KeyId>               # fetch existing key by ID, store it
#
# Output: prints the JSON returned by QConnect to stdout so the caller
# (e.g. `docker exec radius01 qconnect-fetch`) sees it too.
set -eu

QCONNECT_URL="${QCONNECT_URL:-http://qconnect:9000}"
KEYS_FILE="${KEYS_FILE:-/etc/raddb/mods-config/files/keys}"

if [ "$#" -ge 1 ]; then
    key_id="$1"
    echo "[qconnect-fetch] GET ${QCONNECT_URL}/keys/${key_id}" >&2
    json="$(curl -fsS "${QCONNECT_URL}/keys/${key_id}")"
else
    echo "[qconnect-fetch] POST ${QCONNECT_URL}/keys/generate" >&2
    json="$(curl -fsS -X POST "${QCONNECT_URL}/keys/generate")"
fi

# Parse JSON
KEY_ID="$(printf '%s' "$json" | jq -r '.KeyId')"
KEY="$(printf '%s' "$json" | jq -r '.Key')"

if [ -z "$KEY_ID" ] || [ "$KEY_ID" = "null" ] || \
   [ -z "$KEY" ]    || [ "$KEY" = "null" ]; then
    echo "[qconnect-fetch] ERROR: unexpected response: $json" >&2
    exit 1
fi

# Append in the same format FreeRADIUS uses for `authorize`:
#   <user>   Cleartext-Password := "<password>"
# Skip if the KeyId is already present (idempotent).
if grep -qE "^${KEY_ID}[[:space:]]" "$KEYS_FILE" 2>/dev/null; then
    echo "[qconnect-fetch] ${KEY_ID} already present in ${KEYS_FILE}, not appending." >&2
else
    printf '%-32s Cleartext-Password := "%s"\n' "$KEY_ID" "$KEY" >> "$KEYS_FILE"
    echo "[qconnect-fetch] appended ${KEY_ID} to ${KEYS_FILE}" >&2
fi

# Echo the JSON so callers can pipe it into other tools.
printf '%s\n' "$json"

