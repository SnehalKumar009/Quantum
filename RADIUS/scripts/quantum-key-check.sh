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
# Stdout (FreeRADIUS captures this):
#   "OK"                       -> keys match, allow
#   "FAIL:<reason>"            -> any failure (missing args, QConnect down,
#                                  KeyId not found, key mismatch)
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

if [ -z "$KEY_ID" ] || [ -z "$SUPPLIED_KEY" ]; then
    echo "FAIL:missing-args"
    exit 0
fi

# Fetch the key record. -f makes curl exit non-zero on HTTP >=400 (e.g. 404).
resp="$(curl -fsS --max-time 3 "${QCONNECT_URL}/keys/${KEY_ID}" 2>/dev/null)" || {
    echo "FAIL:qconnect-unreachable-or-keyid-not-found"
    exit 0
}

stored_key="$(printf '%s' "$resp" | jq -r '.Key' 2>/dev/null)"
if [ -z "$stored_key" ] || [ "$stored_key" = "null" ]; then
    echo "FAIL:no-Key-in-response"
    exit 0
fi

# Case-insensitive hex compare.
sk="$(printf '%s' "$stored_key"   | tr 'A-Z' 'a-z')"
xk="$(printf '%s' "$SUPPLIED_KEY" | tr 'A-Z' 'a-z')"

if [ "$sk" = "$xk" ]; then
    echo "OK"
else
    echo "FAIL:key-mismatch"
fi
exit 0

