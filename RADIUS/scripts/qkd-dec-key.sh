#!/bin/sh
# =============================================================================
# qkd-dec-key  -  Retrieve a QKD key from qConnect by (master_SAE_ID, key_ID).
#
# Args:
#   $1 = master_SAE_ID   (UUID of the SAE that called enc_keys)
#   $2 = key_ID          (UUID returned by that enc_keys call)
#
# Stdout (only if success):
#   the JSON body returned by the KME
#
# Exit codes:
#   0  - HTTP 200 AND JSON body contains .keys[0].key
#   1  - missing args / missing certs / KME unreachable / non-200 / no .key
#
# Stderr + /tmp/qkd-dec-key.log: loud trace lines for debugging.
#
# Env (defaults assume the standard /etc/qkd bundle layout):
#   QKD_KME_URL    e.g. https://192.168.10.233:50555
#   QKD_CERT       /etc/qkd/sae-radius01.crt.pem
#   QKD_KEY        /etc/qkd/sae-radius01.key.pem
#   QKD_CACERT     /etc/qkd/sae-radius01.trusted_cas.pem
# =============================================================================
set -u

# FreeRADIUS's rlm_exec strips most of the parent env when it forks children,
# so the QKD_* vars set by docker-compose may not be visible here. The radius
# entrypoint persists them to /etc/qkd-env at container boot — source it now
# (no-op if it doesn't exist).
[ -r /etc/qkd-env ] && . /etc/qkd-env

MASTER_SAE_ID="${1:-}"
KEY_ID="${2:-}"
LOGFILE="/tmp/qkd-dec-key.log"
TS="$(date '+%Y-%m-%d %H:%M:%S')"

_trace() {
    printf '%s [qkd-dec-key] %s\n' "$TS" "$1" >&2
    printf '%s [qkd-dec-key] %s\n' "$TS" "$1" >> "$LOGFILE" 2>/dev/null || true
}

_trace "==================== qkd-dec-key invocation ===================="
_trace "ARG  master_SAE_ID='${MASTER_SAE_ID}'"
_trace "ARG  key_ID='${KEY_ID}'"
_trace "ENV  QKD_KME_URL='${QKD_KME_URL:-<unset>}'"
_trace "ENV  QKD_CERT='${QKD_CERT:-<unset>}'"
_trace "ENV  QKD_KEY='${QKD_KEY:-<unset>}'"
_trace "ENV  QKD_CACERT='${QKD_CACERT:-<unset>}'"

if [ -z "$MASTER_SAE_ID" ] || [ -z "$KEY_ID" ]; then
    _trace "FAIL missing args"
    exit 1
fi
if [ -z "${QKD_KME_URL:-}" ]; then
    _trace "FAIL QKD_KME_URL unset"
    exit 1
fi
for f in "${QKD_CERT:-}" "${QKD_KEY:-}" "${QKD_CACERT:-}"; do
    if [ -z "$f" ] || [ ! -r "$f" ]; then
        _trace "FAIL missing or unreadable file: '$f'"
        exit 1
    fi
done

URL="${QKD_KME_URL%/}/api/v1/keys/${MASTER_SAE_ID}/dec_keys?key_ID=${KEY_ID}"
_trace "GET  ${URL}"

http_status="$(curl -sS \
                    --max-time 5 \
                    --cert    "$QKD_CERT" \
                    --key     "$QKD_KEY" \
                    --cacert  "$QKD_CACERT" \
                    -o /tmp/qkd_dec_resp.$$ \
                    -w '%{http_code}' \
                    "$URL" 2>/tmp/qkd_dec_err.$$ \
                || echo '000')"
resp="$(cat /tmp/qkd_dec_resp.$$ 2>/dev/null)"
curl_err="$(cat /tmp/qkd_dec_err.$$ 2>/dev/null)"
rm -f /tmp/qkd_dec_resp.$$ /tmp/qkd_dec_err.$$

_trace "HTTP status=${http_status}"
[ -n "$curl_err" ] && _trace "CURL stderr=${curl_err}"
_trace "BODY ${resp:-<empty>}"

if [ "$http_status" != "200" ]; then
    _trace "RESULT FAIL (http=${http_status})"
    exit 1
fi

key="$(printf '%s' "$resp" | jq -r '.keys[0].key // empty' 2>/dev/null)"
if [ -z "$key" ]; then
    _trace "RESULT FAIL (no .keys[0].key in body)"
    exit 1
fi

_trace "RESULT OK (retrieved key length=${#key})"
printf '%s\n' "$resp"
exit 0

