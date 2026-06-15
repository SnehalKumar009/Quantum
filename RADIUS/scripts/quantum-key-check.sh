#!/bin/sh
# =============================================================================
# quantum-key-check  -  Validate (KeyId, Key) against QConnect.
#
# Invoked by FreeRADIUS via rlm_exec / %{exec:...} from policy.d/quantum-key-check.
#
# Args:
#   $1 = Quantum-Key-Id   (e.g. qkey-3f8a91b2c0de)
#   $2 = Quantum-Key      (hex, as forwarded by the NAS)
#
# Stdout (FreeRADIUS captures this; must stay clean):
#   "OK"                       -> keys match, allow
#   "FAIL:<reason>"            -> any failure (missing args, QConnect down,
#                                  KeyId not found, key mismatch)
#
# Stderr + /tmp/quantum-key-check.log (debug):
#   Full inputs, raw QConnect response, stored key, comparison verdict.
#   FreeRADIUS in -X mode prints child stderr inline; the file gives you a
#   reliable copy regardless: `docker exec radius01 cat /tmp/quantum-key-check.log`
#
# Always exits 0 so FreeRADIUS reads the stdout result rather than treating
# a non-zero exit as a module error. Policy decides accept/reject from stdout.
#
# Env:
#   QCONNECT_URL   default http://qconnect:9000
# =============================================================================
set -u

KEY_ID="${1:-}"
SUPPLIED_KEY="${2:-}"
QCONNECT_URL="${QCONNECT_URL:-http://qconnect:9000}"
LOGFILE="/tmp/quantum-key-check.log"
TS="$(date '+%Y-%m-%d %H:%M:%S')"

# Log to stderr + file. Stdout is reserved for the FR result token.
_log() {
    printf '%s [quantum-key-check] %s\n' "$TS" "$1" >&2
    printf '%s [quantum-key-check] %s\n' "$TS" "$1" >> "$LOGFILE" 2>/dev/null || true
}

_log "------ new invocation ------"
_log "INPUT   KeyId='${KEY_ID}'  SuppliedKey='${SUPPLIED_KEY}'  (len=${#SUPPLIED_KEY})"
_log "TARGET  ${QCONNECT_URL}/keys/${KEY_ID}"

# ---------------------------------------------------------------------------
# Best-effort trace probe against the REAL qConnect KME (ETSI GS QKD 014).
# Never affects the auth verdict — purely diagnostic. Writes to
# /tmp/qkd-status.log and to FreeRADIUS -X stderr so you can see it inline.
# ---------------------------------------------------------------------------
if [ -x /usr/local/bin/qkd-status ] && [ -n "${QKD_KME_URL:-}" ]; then
    _log "PROBE   /usr/local/bin/qkd-status (target=${QKD_KME_URL})"
    /usr/local/bin/qkd-status >/dev/null 2>>"$LOGFILE" || true
fi

if [ -z "$KEY_ID" ] || [ -z "$SUPPLIED_KEY" ]; then
    _log "RESULT  FAIL:missing-args"
    echo "FAIL:missing-args"
    exit 0
fi

# Capture body + HTTP status separately so we can log both.
http_status="$(curl -sS -o /tmp/qkey_resp.$$ -w '%{http_code}' \
                    --max-time 3 "${QCONNECT_URL}/keys/${KEY_ID}" 2>/tmp/qkey_err.$$ \
                || echo '000')"
resp="$(cat /tmp/qkey_resp.$$ 2>/dev/null)"
curl_err="$(cat /tmp/qkey_err.$$ 2>/dev/null)"
rm -f /tmp/qkey_resp.$$ /tmp/qkey_err.$$

_log "HTTP    status=${http_status}"
[ -n "$curl_err" ] && _log "CURL    stderr=${curl_err}"
_log "BODY    ${resp:-<empty>}"

if [ "$http_status" != "200" ]; then
    _log "RESULT  FAIL:qconnect-unreachable-or-keyid-not-found  (http_status=${http_status})"
    echo "FAIL:qconnect-unreachable-or-keyid-not-found"
    exit 0
fi

stored_key="$(printf '%s' "$resp" | jq -r '.Key' 2>/dev/null)"
if [ -z "$stored_key" ] || [ "$stored_key" = "null" ]; then
    _log "RESULT  FAIL:no-Key-in-response  (body lacked .Key)"
    echo "FAIL:no-Key-in-response"
    exit 0
fi

_log "STORED  Key='${stored_key}'  (len=${#stored_key})"

# Case-insensitive hex compare.
sk="$(printf '%s' "$stored_key"   | tr 'A-Z' 'a-z')"
xk="$(printf '%s' "$SUPPLIED_KEY" | tr 'A-Z' 'a-z')"

_log "COMPARE supplied(lc)='${xk}'"
_log "        stored  (lc)='${sk}'"

if [ "$sk" = "$xk" ]; then
    _log "RESULT  OK    (keys match for KeyId='${KEY_ID}')"
    echo "OK"
else
    _log "RESULT  FAIL:key-mismatch"
    echo "FAIL:key-mismatch"
fi
exit 0



