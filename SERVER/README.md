# server01 — Quantum Secure Lab (Python, Dockerized)

TLS application server in the lab. On startup it **registers with
QConnect** for a fresh `(KeyId, Key)`, **authenticates through the NAS**
(`radius-client`), generates a self-signed TLS cert on first boot, then
listens on `:8443` for `client01` connections.

Per connection: receive QC → send QS → derive session key → decrypt
business message → send encrypted ack.

## Layout

```text
SERVER/
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh            # generates self-signed cert on first run
├── requirements.txt         # requests, cryptography
├── .dockerignore
├── README.md
└── app/
    ├── __init__.py
    ├── main.py              # QConnect register -> NAS auth -> serve_forever
    ├── config.py
    ├── qconnect_client.py   # POST /keys/generate on boot
    ├── nas_auth.py          # POST /auth to radius-client
    ├── tls_server.py        # TLS listener + per-conn protocol
    ├── framing.py
    ├── quantum.py           # QS generator (Phase 4 placeholder)
    └── crypto_session.py    # SHA-256 + AES-GCM
```

## Boot workflow

```text
1. entrypoint.sh: generate self-signed cert at /app/certs/{server.crt,server.key}
                  (first boot only; persisted in named volume server01-certs)

2. POST {QCONNECT_URL}/keys/generate  -> {"KeyId","Key"}

3. POST {NAS_URL}/auth
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

## Configuration (env vars)

| Variable           | Default                       | Description                              |
| ------------------ | ----------------------------- | ---------------------------------------- |
| `USERNAME`         | `server01`                    | RADIUS identity (forwarded by NAS)       |
| `PASSWORD`         | `serverPassword`              |                                          |
| `NAS_URL`          | `http://radius-client:8082`   | Where the NAS lives                      |
| `NAS_SHARED_TOKEN` | `lab-nas-token`               | Bearer token expected by NAS             |
| `QCONNECT_URL`     | `http://qconnect:9000`        |                                          |
| `LISTEN_HOST`      | `0.0.0.0`                     |                                          |
| `LISTEN_PORT`      | `8443`                        |                                          |
| `CERT_DIR`         | `/app/certs`                  | Where the auto-gen cert is stored        |
| `CERT_CN`          | `server01`                    | CN/SAN baked into the cert               |
| `LOG_LEVEL`        | `INFO`                        |                                          |

## Exit codes

| Code | Meaning                              |
| ---- | ------------------------------------ |
| `0`  | Clean shutdown                       |
| `2`  | NAS auth failure (won't serve)       |
| `3`  | QConnect registration failure        |
| `1`  | Any other crash                      |

## Run on its own

```bash
docker compose up -d --build radius01 qconnect radius-client     # deps
cd SERVER
docker compose up --build
```

## End-to-end smoke test

From the repo root (simplest):

```bash
docker compose up --build
```

Server log per `client01` run:

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

## Next steps

- Replace `quantum.generate_quantum_random` with the real RNG/QRNG.
- Move self-signed cert generation to a lab CA (so `client01` can run
  with `TLS_VERIFY=true`).
- Require client certs (`ctx.verify_mode = ssl.CERT_REQUIRED`) for mTLS.

