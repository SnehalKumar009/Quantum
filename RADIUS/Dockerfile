# FreeRADIUS server for the Quantum Secure Client/Server Lab
# Base: official FreeRADIUS 3.x image
FROM freeradius/freeradius-server:3.2.5

LABEL project="quantum-secure-lab" \
      component="radius01" \
      description="RADIUS (AAA) server for client01 and server01"

# Tools needed by the qconnect-fetch helper script (curl + jq).
# The base image is Debian-based, so apt-get is available.
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl jq ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Copy our custom configuration over the defaults shipped in the image.
# The image's config root is /etc/raddb.
COPY raddb/clients.conf                       /etc/raddb/clients.conf
COPY raddb/mods-config/files/authorize        /etc/raddb/mods-config/files/authorize
# Seed file for QConnect-issued key-id/key pairs. Same line format as
# `authorize` so anyone familiar with FreeRADIUS users files recognises it.
COPY raddb/mods-config/files/keys             /etc/raddb/mods-config/files/keys

# Quantum-Lab vendor dictionary - defines Quantum-Key-Id / Quantum-Key VSAs
# (vendor ID 99999) so FreeRADIUS can parse and log them in Access-Requests
# coming from radius-client. We append an $INCLUDE to the main dictionary.
COPY raddb/dictionary.quantum-lab             /etc/raddb/dictionary.quantum-lab
RUN echo '$INCLUDE dictionary.quantum-lab' >> /etc/raddb/dictionary

# Helper that curls QConnect, parses the JSON, and appends a new line to
# /etc/raddb/mods-config/files/keys in the same format as `authorize`.
COPY scripts/qconnect-fetch.sh /usr/local/bin/qconnect-fetch
RUN sed -i 's/\r$//' /usr/local/bin/qconnect-fetch \
 && chmod +x /usr/local/bin/qconnect-fetch

# -----------------------------------------------------------------------------
# Quantum-Key validation against QConnect (POC enhancement).
#
# 1. Helper script `/usr/local/bin/quantum-key-check` that curls QConnect's
#    /keys/{KeyId} and compares the stored Key to the one sent in the VSA.
# 2. Policy file `/etc/raddb/policy.d/quantum-key-check` defining the
#    `quantum_key_check` policy invoked from authorize {}.
# 3. Inject a call to that policy at the top of the `authorize` section in
#    sites-enabled/default so it runs before pap and can short-circuit with
#    Access-Reject on any failure. Uses the symlink target to be safe.
# -----------------------------------------------------------------------------
COPY scripts/quantum-key-check.sh /usr/local/bin/quantum-key-check
RUN sed -i 's/\r$//' /usr/local/bin/quantum-key-check \
 && chmod +x /usr/local/bin/quantum-key-check

# Real qConnect (ETSI 014) status probe over mTLS. Invoked from
# quantum-key-check as a best-effort trace step.
COPY scripts/qkd-status.sh /usr/local/bin/qkd-status
RUN sed -i 's/\r$//' /usr/local/bin/qkd-status \
 && chmod +x /usr/local/bin/qkd-status

COPY raddb/policy.d/quantum-key-check /etc/raddb/policy.d/quantum-key-check
RUN sed -i 's/\r$//' /etc/raddb/policy.d/quantum-key-check

# The %{exec:...} xlat used by the quantum_key_check policy needs the default
# `exec` module instance to be configured with `wait = yes` (so FreeRADIUS
# actually captures stdout). The stock module ships with `wait = no`, which
# silently expands to "" and makes every legitimate auth get rejected with
# "Quantum-Key validation failed". Flip it via sed on the resolved file (the
# entry in mods-enabled is a symlink into mods-available).
RUN target="$(readlink -f /etc/raddb/mods-enabled/exec)" \
 && sed -i 's/^[[:space:]]*wait[[:space:]]*=.*/\twait = yes/' "$target" \
 && grep -E '^\s*wait\s*=' "$target"

# Inject `quantum_key_check` as the first statement inside `authorize {`
# in the default virtual server. Idempotent: only inserts if not already there.
RUN target="$(readlink -f /etc/raddb/sites-enabled/default)" \
 && grep -q 'quantum_key_check' "$target" \
    || sed -i '0,/^authorize {/{s/^authorize {/authorize {\n\tquantum_key_check/}' "$target"

# Standard RADIUS ports
EXPOSE 1812/udp 1813/udp

# -----------------------------------------------------------------------------
# Startup-time qConnect KME smoke probe.
# Runs `qkd-status` once before radiusd takes over so that `docker logs radius01`
# shows the ETSI 014 mTLS round-trip immediately at boot, not only on the first
# auth request. Failure is non-fatal — radiusd starts regardless.
#
# NOTE: the freeradius base image ships the daemon as `freeradius` (with
# `radiusd` sometimes only as a symlink), and /bin/sh's PATH inside this
# script may not include its install dir. So we resolve the binary explicitly.
# -----------------------------------------------------------------------------
RUN printf '%s\n' \
    '#!/bin/sh' \
    'set -u' \
    'echo "[entrypoint] ======== qConnect KME boot probe ========"' \
    'if [ -x /usr/local/bin/qkd-status ] && [ -n "${QKD_KME_URL:-}" ]; then' \
    '    /usr/local/bin/qkd-status || true' \
    'else' \
    '    echo "[entrypoint] qkd-status not runnable or QKD_KME_URL unset; skipping"' \
    'fi' \
    'RADIUSD_BIN="$(command -v freeradius 2>/dev/null || command -v radiusd 2>/dev/null || true)"' \
    'for cand in /usr/sbin/freeradius /usr/sbin/radiusd /opt/freeradius/sbin/freeradius /opt/freeradius/sbin/radiusd; do' \
    '    [ -z "$RADIUSD_BIN" ] && [ -x "$cand" ] && RADIUSD_BIN="$cand"' \
    'done' \
    'if [ -z "$RADIUSD_BIN" ]; then' \
    '    echo "[entrypoint] FATAL: cannot locate freeradius/radiusd binary" >&2' \
    '    exit 127' \
    'fi' \
    'echo "[entrypoint] ======== handing off to $RADIUSD_BIN -X ========"' \
    'exec "$RADIUSD_BIN" -X' \
    > /usr/local/bin/radius-entrypoint \
 && chmod +x /usr/local/bin/radius-entrypoint

# Run in foreground with logging to stdout so `docker logs` works.
# Entrypoint first probes qConnect, then exec's radiusd -X.
CMD ["/usr/local/bin/radius-entrypoint"]



