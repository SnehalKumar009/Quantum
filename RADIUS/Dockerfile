# FreeRADIUS server for the Quantum Secure Client/Server Lab
# Base: official FreeRADIUS 3.x image
FROM freeradius/freeradius-server:3.2.5

LABEL project="quantum-secure-lab" \
      component="radius01" \
      description="RADIUS (AAA) server for client01 and server01"

# Copy our custom configuration over the defaults shipped in the image.
# The image's config root is /etc/raddb.
COPY raddb/clients.conf            /etc/raddb/clients.conf
COPY raddb/mods-config/files/authorize /etc/raddb/mods-config/files/authorize

# Standard RADIUS ports
EXPOSE 1812/udp 1813/udp

# Run in foreground with logging to stdout so `docker logs` works.
# -X = full debug. Switch to -f for production-quiet mode.
CMD ["radiusd", "-X"]

