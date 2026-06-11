# Quantum Secure Client/Server Lab

See [`Architecture.md`](./Architecture.md) for the design.

## Requirements

- **Docker Desktop** on Windows / macOS, or Docker Engine + Compose v2 on
  Linux.
- Nothing else. No local Python, no OpenSSL, no `radtest`.

## Run the whole lab (one command)

From this folder:

```bash
docker compose up --build
```

Order is handled automatically:

1. `radius01` (FreeRADIUS) and `qconnect` (key store) start.
2. `client-radiusclient` and `server-radiusclient` (the two NAS instances)
   start and pass their `/healthz` probe.
3. `server01` boots, registers with QConnect, authenticates via
   `server-radiusclient`, generates a self-signed TLS cert, listens on
   `:8443`.
4. `client01` runs once: register with QConnect → authenticate via
   `client-radiusclient` → TLS to `server01` → quantum exchange →
   encrypted message → exit `0`.
5. `radius-ui` available at <http://localhost:8081>.

Stop everything:

```bash
docker compose down          # remove containers + network
docker compose down -v       # also wipe the cert / qconnect volumes
```

## Run components individually

Each folder has its own `docker-compose.yml` and brings up its own
dependencies (e.g. `CLIENT/docker-compose.yml` also starts
`client-radiusclient`). Order:

```bash
cd RADIUS    && docker compose up -d --build && cd ..
cd QConnect  && docker compose up -d --build && cd ..
cd RADIUS_UI && docker compose up -d --build && cd ..
cd SERVER    && docker compose up -d --build && cd ..    # also starts server-radiusclient
cd CLIENT    && docker compose up    --build && cd ..    # also starts client-radiusclient
```

When run this way, RADIUS must come up first because it owns the
`quantum-net` Docker network that the others attach to as `external`.

## Folder map

| Folder          | Component         | Image tag                                  | Exposed |
| --------------- | ----------------- | ------------------------------------------ | ------- |
| `RADIUS/`       | FreeRADIUS 3.2.5  | `quantum-lab/radius01:latest`              | udp 1812/1813 |
| `RADIUS_CLIENT/`| NAS image source  | `quantum-lab/{client,server}-radiusclient:latest` (built twice from this folder) | internal |
| `SERVER/`       | Python TLS srv    | `quantum-lab/server01:latest`              | tcp 8443 |
| `CLIENT/`       | Python client     | `quantum-lab/client01:latest`              | – (one-shot) |
| `RADIUS_UI/`    | FastAPI web UI    | `quantum-lab/radius-ui:latest`             | tcp 8081 |
| `QConnect/`     | RNG / key store   | `quantum-lab/qconnect:latest`              | tcp 9000 |

## Boot flow

```
qconnect ──┐                                                  ┌─ radius01 (FreeRADIUS)
           │                                                  │
           │   POST /keys/generate                            │
client01 ──┤────────────────┐                                 │  RADIUS over UDP
server01 ──┘                ▼                                 │
                  client-radiusclient (NAS for client01) ─────┤
                  server-radiusclient (NAS for server01) ─────┘

client01 / server01 then:
   POST http://<their-nas>:8082/auth
        { username, password, KeyId, Key }   (Authorization: Bearer lab-nas-token)
   → NAS forwards to radius01 with User-Name + User-Password + VSAs
     Quantum-Key-Id (99999.1) and Quantum-Key (99999.2).
```

After successful auth, `client01` ↔ `server01` do TLS + quantum exchange +
AES-GCM as before.

## Default credentials

| Username   | Password         |
| ---------- | ---------------- |
| `client01` | `clientPassword` |
| `server01` | `serverPassword` |

RADIUS shared secret: `testing123`. NAS bearer token: `lab-nas-token`.

## Windows note

`SERVER/entrypoint.sh` must keep **LF** line endings; `.gitattributes`
enforces this and the Dockerfile strips any stray CR as a belt-and-braces
fix. If you ever see `exec format error` from `entrypoint.sh`, that's why.

