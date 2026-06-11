# RADIUS (radius01) — Quantum Secure Lab

FreeRADIUS 3.x server providing **Authentication, Authorization, and Accounting (AAA)** for
`client01` and `server01` containers, per `Architecture.md`.

## Layout

```text
RADIUS/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── README.md
└── raddb/
    ├── clients.conf                 # which NAS/clients may talk to us
    └── mods-config/
        └── files/
            └── authorize            # user accounts (client01, server01, testuser)
```

Only the files we *override* live in `raddb/`. Everything else is inherited from the
official `freeradius/freeradius-server:3.2.5` image's default `/etc/raddb`.

## Initial Accounts

| Username   | Password         | Notes                  |
| ---------- | ---------------- | ---------------------- |
| `client01` | `clientPassword` | App client identity    |
| `server01` | `serverPassword` | App server identity    |
| `testuser` | `testpw`         | For `radtest` smoke check |

Shared secret (all clients): **`testing123`**

## Build & Run

From this `RADIUS/` directory:

```powershell
docker compose up --build
```

Container will start in **debug mode** (`radiusd -X`) so you can watch every packet in
`docker logs`. Stop with `Ctrl+C` (or `docker compose down`).

The container is published on the host:

- `udp/1812` — authentication
- `udp/1813` — accounting

It also joins the user-defined Docker network **`quantum-net`**, which `client01` and
`server01` will join later so they can reach it by hostname `radius01`.

## Smoke Test from the Host

Install a RADIUS test client (e.g. `freeradius-utils` on Linux, or run one from a
throwaway container) and run:

```bash
# From any machine that can reach the host on udp/1812
radtest testuser testpw 127.0.0.1 0 testing123
radtest client01 clientPassword 127.0.0.1 0 testing123
radtest server01 serverPassword 127.0.0.1 0 testing123
```

Expected: `Received Access-Accept`.

## Smoke Test from Another Container

Once `client01` / `server01` exist on `quantum-net`:

```bash
docker run --rm --network quantum-net freeradius/freeradius-server:3.2.5 \
    radtest client01 clientPassword radius01 0 testing123
```

## Switching to Production Mode

Edit the `CMD` in `Dockerfile`:

```dockerfile
CMD ["radiusd", "-f"]   # foreground, normal logging
```

## Next Phases

- **Phase 2:** TLS between `client01` and `server01` (not RADIUS-related).
- **Phase 3:** `client01` and `server01` perform RADIUS auth against this server before
  establishing their TLS session.
- Later: move `radius01` to its own Ubuntu host and tighten `clients.conf` to only the
  specific peer IPs.

