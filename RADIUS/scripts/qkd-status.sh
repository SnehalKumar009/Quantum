#!/bin/sh
# =============================================================================
# qkd-status  -  Probe the real qConnect KME (ETSI GS QKD 014) over mTLS.
#
# Invokes:
#   GET ${QKD_KME_URL}/api/v1/keys/<peer-SAE-ID>/status
# using the SAE's client certificate + key + CA bundle.
#
# Usage:
#   qkd-status                 # peer SAE = self (smoke test)
#   qkd-status <peer-SAE-ID>   # explicit peer SAE UUID
#
# Stdout: the raw JSON response from the KME (or empty on failure).
# Stderr + /tmp/qkd-status.log: loud trace lines: target URL, HTTP code,
#   curl exit code, response body, parsed fields.
#
# Env (defaults assume the bundle layout under /etc/qkd):
#   QKD_KME_URL    e.g. https://192.168.10.233
#   QKD_CERT       /etc/qkd/<alias>.crt.pem
#   QKD_KEY        /etc/qkd/<alias>.key.pem
#   QKD_CACERT     /etc/qkd/<alias>.trusted_cas.pem
#   QKD_INFO_JSON  /etc/qkd/<alias>.info.json   (used to learn own SAE_ID)
#   QKD_SAE_ID     optional override of own SAE_ID
#
# Always exits 0 so callers can chain this as a pure trace step.
# =============================================================================
set -u

# rlm_exec strips most env vars when FR forks; re-source the QKD_* values
# written by the container entrypoint (no-op outside the radius image).
[ -r /etc/qkd-env ] && . /etc/qkd-env

PEER_ARG="${1:-}"
LOGFILE="/tmp/qkd-status.log"
TS="$(date '+%Y-%m-%d %H:%M:%S')"

_trace() {
    printf '%s [qkd-status] %s\n' "$TS" "$1" >&2
    printf '%s [qkd-status] %s\n' "$TS" "$1" >> "$LOGFILE" 2>/dev/null || true
}

_trace "==================== qkd-status invocation ===================="
_trace "ENV  QKD_KME_URL='${QKD_KME_URL:-<unset>}'"
_trace "ENV  QKD_CERT='${QKD_CERT:-<unset>}'"
_trace "ENV  QKD_KEY='${QKD_KEY:-<unset>}'"
_trace "ENV  QKD_CACERT='${QKD_CACERT:-<unset>}'"
_trace "ENV  QKD_INFO_JSON='${QKD_INFO_JSON:-<unset>}'"

# --- sanity-check that the bundle is actually mounted -----------------------
for f in "${QKD_CERT:-}" "${QKD_KEY:-}" "${QKD_CACERT:-}"; do
    if [ -z "$f" ] || [ ! -r "$f" ]; then
        _trace "FAIL missing or unreadable file: '$f'"
        _trace "     -> is the SAE bundle bind-mounted into /etc/qkd ?"
        exit 0
    fi
done
if [ -z "${QKD_KME_URL:-}" ]; then
    _trace "FAIL QKD_KME_URL is not set"
    exit 0
fi

# --- resolve own SAE_ID from info.json (or env override) --------------------
OWN_SAE_ID="${QKD_SAE_ID:-}"
if [ -z "$OWN_SAE_ID" ] && [ -r "${QKD_INFO_JSON:-/dev/null}" ]; then
    OWN_SAE_ID="$(jq -r '.sae_id // empty' "$QKD_INFO_JSON" 2>/dev/null)"
fi
_trace "SELF SAE_ID='${OWN_SAE_ID:-<unknown>}'"

PEER_SAE_ID="${PEER_ARG:-$OWN_SAE_ID}"
_trace "PEER SAE_ID='${PEER_SAE_ID:-<unknown>}'  (arg='${PEER_ARG:-}')"

if [ -z "$PEER_SAE_ID" ]; then
    _trace "FAIL no peer SAE_ID available (pass as arg or set QKD_SAE_ID)"
    exit 0
fi

URL="${QKD_KME_URL%/}/api/v1/keys/${PEER_SAE_ID}/status"
_trace "GET  ${URL}"

# --- the actual mTLS curl ---------------------------------------------------
http_status="$(curl -sS \
                    --max-time 5 \
                    --cert    "$QKD_CERT" \
                    --key     "$QKD_KEY" \
                    --cacert  "$QKD_CACERT" \
                    -o /tmp/qkd_resp.$$ \
                    -w '%{http_code}' \
                    "$URL" 2>/tmp/qkd_err.$$ \
                || echo '000')"
resp="$(cat /tmp/qkd_resp.$$ 2>/dev/null)"
curl_err="$(cat /tmp/qkd_err.$$ 2>/dev/null)"
rm -f /tmp/qkd_resp.$$ /tmp/qkd_err.$$

_trace "HTTP status=${http_status}"
[ -n "$curl_err" ] && _trace "CURL stderr=${curl_err}"
_trace "BODY ${resp:-<empty>}"

# --- pretty-print key fields if response looks like JSON --------------------
if [ "$http_status" = "200" ] && printf '%s' "$resp" | jq . >/dev/null 2>&1; then
    src="$(printf '%s' "$resp" | jq -r '.source_KME_ID  // empty')"
    tgt="$(printf '%s' "$resp" | jq -r '.target_KME_ID  // empty')"
    ksz="$(printf '%s' "$resp" | jq -r '.key_size       // empty')"
    cnt="$(printf '%s' "$resp" | jq -r '.stored_key_count // empty')"
    _trace "PARSE source_KME_ID=${src}  target_KME_ID=${tgt}  key_size=${ksz}  stored_key_count=${cnt}"
    _trace "RESULT OK"
else
    _trace "RESULT FAIL (http=${http_status})"
fi

# Echo body on stdout so callers can pipe it.
printf '%s\n' "$resp"
exit 0

