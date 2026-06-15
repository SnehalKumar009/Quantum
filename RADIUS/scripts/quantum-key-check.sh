#!/bin/sh
# =============================================================================
# quantum-key-check  -  Authenticate by *fetching* the QKD key from qConnect.
#
# Invoked by FreeRADIUS via rlm_exec / %{exec:...} from
# policy.d/quantum-key-check.
#
# Args:
#   $1 = Quantum-Key-Id          (UUID; returned by enc_keys at the master)
#   $2 = Quantum-Master-SAE-ID   (UUID of the master SAE; needed in dec_keys URL)
#
# Stdout (FreeRADIUS captures this; must stay clean):
#   "OK"                    -> KME returned the key -> allow
#   "FAIL:missing-args"     -> Key-Id or Master-SAE-ID empty
#   "FAIL:helper-missing"   -> /usr/local/bin/qkd-dec-key not installed
#   "FAIL:dec_keys-failed"  -> qkd-dec-key.sh non-zero exit (HTTP !=200, no key)
#
# Stderr + /tmp/quantum-key-check.log:
#   Full inputs, trace of the dec_keys call, verdict.
#
# Always exits 0 so FreeRADIUS reads the stdout result rather than treating
# a non-zero exit as a module error. Policy decides accept/reject from stdout.
#
# Env (forwarded to qkd-dec-key.sh):
#   QKD_KME_URL    e.g. https://192.168.10.233:50555
#   QKD_CERT / QKD_KEY / QKD_CACERT   - radius01's SAE bundle
# =============================================================================
set -u

# rlm_exec strips most env vars — re-source the QKD_* values written by the
# container entrypoint so the trace log shows real values, not <unset>.
[ -r /etc/qkd-env ] && . /etc/qkd-env

KEY_ID="${1:-}"
MASTER_SAE_ID="${2:-}"
LOGFILE="/tmp/quantum-key-check.log"
TS="$(date '+%Y-%m-%d %H:%M:%S')"

_log() {
    printf '%s [quantum-key-check] %s\n' "$TS" "$1" >&2
    printf '%s [quantum-key-check] %s\n' "$TS" "$1" >> "$LOGFILE" 2>/dev/null || true
}

_log "------ new invocation ------"
_log "INPUT  Quantum-Key-Id='${KEY_ID}'  Quantum-Master-SAE-ID='${MASTER_SAE_ID}'"
_log "KME    ${QKD_KME_URL:-<unset>}"

if [ -z "$KEY_ID" ] || [ -z "$MASTER_SAE_ID" ]; then
    _log "RESULT FAIL:missing-args"
    echo "FAIL:missing-args"
    exit 0
fi

if [ ! -x /usr/local/bin/qkd-dec-key ]; then
    _log "RESULT FAIL:helper-missing  (/usr/local/bin/qkd-dec-key not executable)"
    echo "FAIL:helper-missing"
    exit 0
fi

# Run the helper; its stderr already lands in radiusd -X log.
if /usr/local/bin/qkd-dec-key "$MASTER_SAE_ID" "$KEY_ID" >/dev/null 2>>"$LOGFILE"; then
    _log "RESULT OK  (KME returned the key for KeyId=${KEY_ID})"
    echo "OK"
else
    _log "RESULT FAIL:dec_keys-failed"
    echo "FAIL:dec_keys-failed"
fi
exit 0



