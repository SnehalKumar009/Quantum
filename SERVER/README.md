# server01 — Quantum Secure Lab (Python, Dockerized)

TLS application server. On startup:

1. **Registers with QConnect** for a fresh `(KeyId, Key)`.
2. **Authenticates through its own NAS** — `server-radiusclient` —
   which forwards the request as RADIUS to `radius01`.
3. Generates a self-signed TLS cert on first boot.
4. Listens on `:8443` for `client01` connections.

Per connection: receive QC → send QS → derive session key → decrypt
business message → send encrypted ack.

## Containers spun up by `SERVER/docker-compose.yml`

| Container             | Image                                       | Role                                  |
| --------------------- | ------------------------------------------- | ------------------------------------- |
| `server-radiusclient` | `quantum-lab/server-radiusclient:latest`    | NAS dedicated to `server01`           |
| `server01`            | `quantum-lab/server01:latest`               | The application server                |

`server-radiusclient` is built from `../RADIUS_CLIENT/` (same image
source as `client-radiusclient`); only its `container_name`,
`hostname`, and `NAS_IDENTIFIER` differ.

## Layout

```text
SERVER/
├── Dockerfile
├── docker-compose.yml       # defines server-radiusclient + server01
├── entrypoint.sh            # generates self-signed cert on first run
├── requirements.txt         # requests, cryptography
├── .dockerignore
├── README.md
└── app/
    ├── __init__.py
    ├── main.py              # QConnect register -> NAS auth -> serve_forever
    ├── config.py
    ├── qconnect_client.py
    ├── nas_auth.py
    ├── tls_server.py        # TLS listener + per-conn protocol
    ├── framing.py
    ├── quantum.py
    └── crypto_session.py
```

## Boot workflow

```text
1. entrypoint.sh: generate self-signed cert at /app/certs/{server.crt,server.key}
                  (first boot only; persisted in named volume server01-certs)

2. POST {QCONNECT_URL}/keys/generate  -> {"KeyId","Key"}

3. POST {NAS_URL}/auth                          (NAS_URL=http://server-radiusclient:8082)
       Authorization: Bearer {NAS_SHARED_TOKEN}
       {"username":"server01","password":"serverPassword","KeyId","Key"}
       -> 200 OK

4. Listen on {LISTEN_HOST}:{LISTEN_PORT} (TLS 1.2+).
   Per connection (inside the TLS tunnel):
     <- frame(QC, 32B)
     -> frame(QS, 32B)
        SessionKey = SHA-256(QC || QS)
     <- frame(nonce(12) || AES-GCM-ciphertext)
     -> frame(nonce(12) || AES-GCM-ciphertext)   (ack)
```

## Configuration (server01 env vars)

| Variable           | Default                              | Description                              |
| ------------------ | ------------------------------------ | ---------------------------------------- |
| `USERNAME`         | `server01`                           | RADIUS identity (forwarded by NAS)       |
| `PASSWORD`         | `serverPassword`                     |                                          |
| `NAS_URL`          | `http://server-radiusclient:8082`    | Server's dedicated NAS                   |
| `NAS_SHARED_TOKEN` | `lab-nas-token`                      | Bearer token expected by NAS             |
| `QCONNECT_URL`     | `http://qconnect:9000`               |                                          |
| `LISTEN_HOST`      | `0.0.0.0`                            |                                          |
| `LISTEN_PORT`      | `8443`                               |                                          |
| `CERT_DIR`         | `/app/certs`                         |                                          |
| `CERT_CN`          | `server01`                           |                                          |
| `LOG_LEVEL`        | `INFO`                               |                                          |

## Configuration (server-radiusclient env vars)

| Variable           | Default                  |
| ------------------ | ------------------------ |
| `RADIUS_HOST`      | `radius01`               |
| `RADIUS_AUTH_PORT` | `1812`                   |
| `RADIUS_SECRET`    | `testing123`             |
| `NAS_IDENTIFIER`   | `server-radiusclient-01` |
| `NAS_SHARED_TOKEN` | `lab-nas-token`          |
| `LOG_LEVEL`        | `INFO`                   |

## Exit codes (server01)

| Code | Meaning                              |
| ---- | ------------------------------------ |
| `0`  | Clean shutdown                       |
| `2`  | NAS auth failure (won't serve)       |
| `3`  | QConnect registration failure        |
| `1`  | Any other crash                      |

## Run on its own

```bash
docker compose up -d --build radius01 qconnect     # deps from top-level
cd SERVER
docker compose up --build                          # brings up server-radiusclient + server01
```

## Expected log tail

```text
server01 | === server01 starting ===
server01 | Registered with QConnect: KeyId=qkey-...
server01 | NAS auth OK for server01. Reply-Message='Welcome server01'
server01 | TLS listener ready on 0.0.0.0:8443 (cert=/app/certs/server.crt)
server01 | Accepted TLS connection from ('172.x.y.z', NNNNN)
server01.conn... | Received QC (32 bytes)
server01.conn... | Sent QS (32 bytes)
server01.conn... | Derived SessionKey first 8 bytes: ...
server01.conn... | Decrypted message from client: b'Hello from client01'
server01.conn... | Sent encrypted ack (... bytes ciphertext)
```

