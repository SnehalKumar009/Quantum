# server01 — Quantum Secure Lab (Python, Dockerized)

Python application server that implements the `server01` role from
[`../Architecture.md`](../Architecture.md):

1. **Phase 3 — RADIUS auth** against `radius01` on startup (✅)
2. **Phase 2 — TLS listener** on `0.0.0.0:8443` with auto-generated self-signed cert (✅)
3. **Phase 4 — Quantum random** exchange QC ↔ QS (✅, classical placeholder)
4. **Phase 5 — Session key** `SHA-256(QC || QS)` (✅)
5. **Phase 6 — AES-GCM** decrypt of client message + encrypted ack (✅)

## Layout

```text
SERVER/
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh            # auto-generates self-signed TLS cert on first run
├── requirements.txt
├── .dockerignore
├── README.md
└── app/
    ├── __init__.py
    ├── main.py              # RADIUS auth, then serve_forever
    ├── config.py
    ├── radius_auth.py
    ├── radius_dictionary
    ├── tls_server.py        # TLS listener + per-conn protocol
    ├── framing.py           # 4-byte length-prefixed frames
    ├── quantum.py           # Phase 4 placeholder
    └── crypto_session.py    # SHA-256 + AES-GCM
```

## Prerequisites

`radius01` must be running first (it owns the `quantum-net` network):

```powershell
cd ..\RADIUS
docker compose up -d --build
```

## Build & Run server01

```powershell
cd ..\SERVER
docker compose up --build
```

First boot: `entrypoint.sh` generates a self-signed cert at
`/app/certs/server.crt` + `server.key` (persisted in the `server01-certs`
named volume). Subsequent starts reuse it.

## Configuration (env vars)

| Variable                | Default          | Description                              |
| ----------------------- | ---------------- | ---------------------------------------- |
| `RADIUS_HOST`           | `radius01`       | Hostname of RADIUS server                |
| `RADIUS_AUTH_PORT`      | `1812`           |                                          |
| `RADIUS_SECRET`         | `testing123`     |                                          |
| `RADIUS_USERNAME`       | `server01`       |                                          |
| `RADIUS_PASSWORD`       | `serverPassword` |                                          |
| `RADIUS_NAS_IDENTIFIER` | `server01`       |                                          |
| `LISTEN_HOST`           | `0.0.0.0`        | Bind address                             |
| `LISTEN_PORT`           | `8443`           | TLS port                                 |
| `CERT_DIR`              | `/app/certs`     | Where the self-signed cert lives         |
| `CERT_CN`               | `server01`       | CN/SAN baked into the auto-gen cert      |
| `LOG_LEVEL`             | `INFO`           |                                          |

## End-to-End Smoke Test

In three terminals:

```powershell
# 1) RADIUS
cd C:\Users\snkumar\CODE\QUANTUM\RADIUS
docker compose up --build

# 2) Server
cd C:\Users\snkumar\CODE\QUANTUM\SERVER
docker compose up --build

# 3) Client (will auth, TLS-connect, exchange, decrypt ack, exit 0)
cd C:\Users\snkumar\CODE\QUANTUM\CLIENT
docker compose up --build
```

Server log should show, per client run:

```text
[INFO] server01: Accepted TLS connection from ('172.x.y.z', NNNN)
[INFO] server01.conn.x.y.z:NNNN: Received QC (32 bytes)
[INFO] server01.conn.x.y.z:NNNN: Sent QS (32 bytes)
[INFO] server01.conn.x.y.z:NNNN: Derived SessionKey first 8 bytes: ...
[INFO] server01.conn.x.y.z:NNNN: Decrypted message from client: b'Hello from client01'
[INFO] server01.conn.x.y.z:NNNN: Sent encrypted ack (... bytes ciphertext)
```

Client log should show:

```text
[INFO] app.tls_client: TLS connection established to server01:8443 (cipher=...)
[INFO] client01: Received QS (32 bytes)
[INFO] client01: Derived SessionKey ...
[INFO] client01: Sent encrypted business message ...
[INFO] client01: Decrypted server ack: b'ack: Hello from client01'
```

## Next Steps

- **Phase 4 (real):** swap `quantum.generate_quantum_random` for a real QRNG
  call (HTTP API or hardware).
- **TLS verification:** stop auto-generating per-instance certs; issue them
  from a lab CA and have `client01` verify with `TLS_VERIFY=true` +
  `TLS_CA_FILE=/path/to/ca.crt`.
- **mTLS:** require client certs on the listener (`ctx.verify_mode = CERT_REQUIRED`).

