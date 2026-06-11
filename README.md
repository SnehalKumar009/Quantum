# Quantum Secure Client/Server Lab

See [`Architecture.md`](./Architecture.md) for the design.

## Requirements

- **Docker Desktop** on Windows / macOS, or Docker Engine + Compose v2 on Linux.
- Nothing else. No local Python, no OpenSSL, no `radtest`.

## Run the whole lab (one command)

From this folder:

```bash
docker compose up --build
```

Order is handled automatically:

1. `radius01` starts (FreeRADIUS).
2. `server01` boots, RADIUS-auths, generates self-signed TLS cert, listens on `:8443`.
3. Healthcheck waits for the TLS port to accept connections.
4. `client01` runs once: RADIUS auth → TLS → quantum exchange → encrypted message → exit `0`.
5. `radius-ui` (FastAPI) is available at **http://localhost:8081**.

Stop everything:

```bash
docker compose down          # remove containers + network
docker compose down -v       # also wipe the TLS cert volume
```

## Run components individually

Each folder has its own `docker-compose.yml`:

```bash
cd RADIUS    && docker compose up -d --build && cd ..
cd SERVER    && docker compose up -d --build && cd ..
cd RADIUS_UI && docker compose up -d --build && cd ..
cd CLIENT    && docker compose up    --build && cd ..
```

When run individually, RADIUS must come up first because it owns the
`quantum-net` Docker network that the others attach to as `external`.

## Folder map

| Folder       | Component        | Image tag                      | Exposed |
| ------------ | ---------------- | ------------------------------ | ------- |
| `RADIUS/`    | FreeRADIUS 3.2.5 | `quantum-lab/radius01:latest`  | udp 1812/1813 |
| `SERVER/`    | Python TLS srv   | `quantum-lab/server01:latest`  | tcp 8443 |
| `CLIENT/`    | Python client    | `quantum-lab/client01:latest`  | – (one-shot) |
| `RADIUS_UI/` | FastAPI web UI   | `quantum-lab/radius-ui:latest` | tcp 8081 |

## Default credentials

| Username   | Password         |
| ---------- | ---------------- |
| `client01` | `clientPassword` |
| `server01` | `serverPassword` |

RADIUS shared secret: `testing123`.

## Windows note

`SERVER/entrypoint.sh` must keep **LF** line endings; `.gitattributes`
enforces this and the Dockerfile strips any stray CR as a belt-and-braces
fix. If you ever see `exec format error` from `entrypoint.sh`, that's why.

