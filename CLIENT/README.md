# client01 — Quantum Secure Lab (Python, Dockerized)

Python application client that implements the `client01` role from
[`../Architecture.md`](../Architecture.md):

1. **Phase 3 — RADIUS auth** against `radius01` (✅ implemented)
2. **Phase 2 — TLS** to `server01` (🚧 stub)
3. **Phase 4 — Quantum random** exchange QC ↔ QS (🚧 stub - uses `os.urandom` placeholder)
4. **Phase 5 — Session key** `SHA-256(QC || QS)` (✅ implemented)
5. **Phase 6 — Encrypted business payload** with AES-GCM (✅ implemented, local demo)

## Layout

```text
CLIENT/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .dockerignore
├── README.md
└── app/
    ├── __init__.py
    ├── main.py              # workflow entrypoint
    ├── config.py            # env-var driven config
    ├── radius_auth.py       # pyrad-based Access-Request
    ├── radius_dictionary    # minimal RFC 2865 dictionary
    ├── tls_client.py        # Phase 2 placeholder
    ├── quantum.py           # Phase 4 placeholder
    └── crypto_session.py    # Phase 5/6 (SessionKey + AES-GCM)
```

## Prerequisites

The RADIUS container must be running first, because it creates the shared
Docker network `quantum-net`:

```powershell
cd ..\RADIUS
docker compose up -d --build
```

## Build & Run client01

```powershell
cd ..\CLIENT
docker compose up --build
```

Expected output (abbreviated):

```text
client01  | [INFO] client01: === client01 starting ===
client01  | [INFO] app.radius_auth: Authenticating as client01 against RADIUS radius01:1812
client01  | [INFO] app.radius_auth: Access-Accept received for client01. Reply-Message='Welcome client01'
client01  | [WARNING] app.quantum: Using classical os.urandom() as QRNG placeholder ...
client01  | [INFO] client01: Generated QC (32 bytes)
client01  | [WARNING] app.tls_client: TLS + quantum exchange not yet implemented ...
client01  | [INFO] client01: Received QS (32 bytes)
client01  | [INFO] client01: Derived SessionKey (sha256, 32 bytes) - first 8 bytes: ...
client01  | [INFO] client01: Encrypted demo message: nonce=... ct=...
client01  | [INFO] client01: === client01 finished successfully ===
```

Exit code:

- `0` — success
- `2` — RADIUS auth failure

## Configuration (env vars)

| Variable                | Default          | Description                              |
| ----------------------- | ---------------- | ---------------------------------------- |
| `RADIUS_HOST`           | `radius01`       | Hostname of RADIUS server                |
| `RADIUS_AUTH_PORT`      | `1812`           | UDP auth port                            |
| `RADIUS_SECRET`         | `testing123`     | Shared secret (must match `clients.conf`)|
| `RADIUS_USERNAME`       | `client01`       | Identity                                 |
| `RADIUS_PASSWORD`       | `clientPassword` | Credential                               |
| `RADIUS_NAS_IDENTIFIER` | `client01`       | NAS-Identifier attribute                 |
| `SERVER_HOST`           | `server01`       | App server hostname (Phase 2+)           |
| `SERVER_PORT`           | `8443`           | App server TLS port (Phase 2+)           |
| `LOG_LEVEL`             | `INFO`           | `DEBUG` for verbose pyrad output         |

Override at run time:

```powershell
docker compose run --rm -e LOG_LEVEL=DEBUG client01
```

## Local Development (without Docker)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:RADIUS_HOST = "127.0.0.1"      # if radius01 ports are published
python -m app.main
```

## Next Steps

- **Phase 2:** Implement `tls_client.exchange_quantum_over_tls()` with a real
  TLS connection (verify `server01`'s cert against a lab CA).
- **Phase 4:** Replace `quantum.generate_quantum_random()` with the real QRNG
  provider (HTTP API, hardware device, etc.).
- Add a `server01` Python project (mirrors this one) that listens on TLS,
  produces QS, and decrypts inbound messages.

