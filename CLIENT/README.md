# client01 — Quantum Secure Lab (Python, Dockerized)

Supplicant. On startup:

1. **Registers with QConnect** for a fresh `(KeyId, Key)`.
2. **Authenticates through its own NAS** — `client-radiusclient` —
   which forwards the request as RADIUS to `radius01`.
3. Opens a TLS session to `server01`, derives a session key from
   quantum-random material, sends an AES-GCM-protected message.

## Containers spun up by `CLIENT/docker-compose.yml`

| Container             | Image                                       | Role                                  |
| --------------------- | ------------------------------------------- | ------------------------------------- |
| `client-radiusclient` | `quantum-lab/client-radiusclient:latest`    | NAS dedicated to `client01`           |
| `client01`            | `quantum-lab/client01:latest`               | The supplicant itself                 |

`client-radiusclient` is built from `../RADIUS_CLIENT/` (same image
source as `server-radiusclient`); only its `container_name`,
`hostname`, and `NAS_IDENTIFIER` differ.

## Layout

```text
CLIENT/
├── Dockerfile
├── docker-compose.yml            # defines client-radiusclient + client01
├── requirements.txt              # requests, cryptography
├── .dockerignore
├── README.md
└── app/
    ├── __init__.py
    ├── main.py                   # workflow entrypoint
    ├── config.py                 # env-var driven config
    ├── qconnect_client.py        # POST /keys/generate on boot
    ├── nas_auth.py               # POST /auth to client-radiusclient
    ├── tls_client.py             # TLS connect + framed I/O
    ├── framing.py                # 4-byte length-prefixed frames
    ├── quantum.py                # QC generator (Phase 4 placeholder)
    └── crypto_session.py         # SHA-256 + AES-GCM
```

## Boot workflow

```text
1. POST {QCONNECT_URL}/keys/generate
       -> {"KeyId":"qkey-...", "Key":"<64 hex>"}

2. POST {NAS_URL}/auth                          (NAS_URL=http://client-radiusclient:8082)
       Authorization: Bearer {NAS_SHARED_TOKEN}
       {"username","password","KeyId","Key"}
       -> 200 {"ok": true, "reply_message": "Welcome client01"}

3. Generate QC (32 bytes, Phase 4 placeholder uses os.urandom)
4. TLS connect to {SERVER_HOST}:{SERVER_PORT}
5. Exchange QC <-> QS  ->  SessionKey = SHA-256(QC || QS)
6. Send AES-GCM(plaintext); receive + decrypt server ack; exit 0.
```

## Configuration (client01 env vars)

| Variable           | Default                              | Description                              |
| ------------------ | ------------------------------------ | ---------------------------------------- |
| `USERNAME`         | `client01`                           | RADIUS identity (forwarded by NAS)       |
| `PASSWORD`         | `clientPassword`                     |                                          |
| `NAS_URL`          | `http://client-radiusclient:8082`    | Client's dedicated NAS                   |
| `NAS_SHARED_TOKEN` | `lab-nas-token`                      | Bearer token expected by NAS             |
| `QCONNECT_URL`     | `http://qconnect:9000`               |                                          |
| `SERVER_HOST`      | `server01`                           | TLS target                               |
| `SERVER_PORT`      | `8443`                               |                                          |
| `TLS_VERIFY`       | `false`                              | Set `true` for proper PKI                |
| `TLS_CA_FILE`      | (unset)                              | Required when `TLS_VERIFY=true`          |
| `LOG_LEVEL`        | `INFO`                               | `DEBUG` for full HTTP/TLS trace          |

## Configuration (client-radiusclient env vars)

| Variable           | Default                  |
| ------------------ | ------------------------ |
| `RADIUS_HOST`      | `radius01`               |
| `RADIUS_AUTH_PORT` | `1812`                   |
| `RADIUS_SECRET`    | `testing123`             |
| `NAS_IDENTIFIER`   | `client-radiusclient-01` |
| `NAS_SHARED_TOKEN` | `lab-nas-token`          |
| `LOG_LEVEL`        | `INFO`                   |

## Exit codes (client01)

| Code | Meaning                              |
| ---- | ------------------------------------ |
| `0`  | Success                              |
| `2`  | NAS auth failure (Access-Reject etc) |
| `3`  | QConnect registration failure        |
| `1`  | Any other crash                      |

## Run on its own

The rest of the stack must be running first (top-level compose is
simplest):

```bash
docker compose up -d --build radius01 qconnect server01
cd CLIENT
docker compose up --build       # brings up client-radiusclient + client01
```

Re-run only the supplicant:

```bash
docker compose run --rm client01
docker compose run --rm -e LOG_LEVEL=DEBUG client01
docker compose run --rm -e PASSWORD=wrong client01     # forces exit 2
```

## Expected log tail

```text
client01 | === client01 starting ===
client01 | Registered with QConnect: KeyId=qkey-...  (64-char hex key)
client01 | Authenticating via NAS http://client-radiusclient:8082/auth as client01 (KeyId=qkey-...)
client01 | NAS auth OK for client01. Reply-Message='Welcome client01'
client01 | Generated QC (32 bytes)
client01 | TLS connection established to server01:8443 (cipher=('TLS_AES_256_GCM_SHA384','TLSv1.3',256))
client01 | Received QS (32 bytes)
client01 | Derived SessionKey (sha256, 32 bytes) - first 8 bytes: ...
client01 | Sent encrypted business message (19 bytes plaintext)
client01 | Decrypted server ack: b'ack: Hello from client01'
client01 | === client01 finished successfully ===
```

