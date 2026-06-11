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

# Helper that curls QConnect, parses the JSON, and appends a new line to
# /etc/raddb/mods-config/files/keys in the same format as `authorize`.
COPY scripts/qconnect-fetch.sh /usr/local/bin/qconnect-fetch
RUN sed -i 's/\r$//' /usr/local/bin/qconnect-fetch \
 && chmod +x /usr/local/bin/qconnect-fetch

# Standard RADIUS ports
EXPOSE 1812/udp 1813/udp

# Run in foreground with logging to stdout so `docker logs` works.
# -X = full debug. Switch to -f for production-quiet mode.
CMD ["radiusd", "-X"]



