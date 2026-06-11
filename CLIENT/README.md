# client01 — Quantum Secure Lab (Python, Dockerized)

Supplicant in the lab. On startup it **registers with QConnect** for a
fresh `(KeyId, Key)`, **authenticates through the NAS** (`radius-client`),
then opens a TLS session to `server01`, derives a session key from
quantum-random material, and sends an AES-GCM-protected message.

## Layout

```text
CLIENT/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt              # requests, cryptography
├── .dockerignore
├── README.md
└── app/
    ├── __init__.py
    ├── main.py                   # workflow entrypoint
    ├── config.py                 # env-var driven config
    ├── qconnect_client.py        # POST /keys/generate on boot
    ├── nas_auth.py               # POST /auth to radius-client
    ├── tls_client.py             # TLS connect + framed I/O
    ├── framing.py                # 4-byte length-prefixed frames
    ├── quantum.py                # QC generator (stub, see Phase 4)
    └── crypto_session.py         # SHA-256 + AES-GCM
```

## Boot workflow

```text
1. POST {QCONNECT_URL}/keys/generate
       -> {"KeyId":"qkey-...", "Key":"<64 hex>"}

2. POST {NAS_URL}/auth
       Authorization: Bearer {NAS_SHARED_TOKEN}
       {"username","password","KeyId","Key"}
       -> 200 {"ok": true, "reply_message": "Welcome client01"}

3. Generate QC (32 bytes; Phase 4 placeholder uses os.urandom)

4. TLS connect to {SERVER_HOST}:{SERVER_PORT}

5. Exchange QC <-> QS  ->  SessionKey = SHA-256(QC || QS)

6. Send AES-GCM(plaintext); receive + decrypt server ack; exit 0.
```

## Configuration (env vars)

| Variable           | Default                       | Description                              |
| ------------------ | ----------------------------- | ---------------------------------------- |
| `USERNAME`         | `client01`                    | RADIUS identity (forwarded by NAS)       |
| `PASSWORD`         | `clientPassword`              |                                          |
| `NAS_URL`          | `http://radius-client:8082`   | Where the NAS lives                      |
| `NAS_SHARED_TOKEN` | `lab-nas-token`               | Bearer token expected by NAS             |
| `QCONNECT_URL`     | `http://qconnect:9000`        | Where to register                        |
| `SERVER_HOST`      | `server01`                    | TLS target                               |
| `SERVER_PORT`      | `8443`                        |                                          |
| `TLS_VERIFY`       | `false`                       | Set `true` for proper PKI                |
| `TLS_CA_FILE`      | (unset)                       | Required when `TLS_VERIFY=true`          |
| `LOG_LEVEL`        | `INFO`                        | `DEBUG` for full HTTP/TLS trace          |

## Exit codes

| Code | Meaning                              |
| ---- | ------------------------------------ |
| `0`  | Success (auth + TLS + ack OK)        |
| `2`  | NAS auth failure (Access-Reject etc) |
| `3`  | QConnect registration failure        |
| `1`  | Any other crash (import, TLS, ...)   |

## Build & Run client01

The rest of the stack must be running first (or use the top-level compose):

```bash
docker compose up -d --build radius01 qconnect radius-client server01
```

Then:

```bash
cd CLIENT
docker compose up --build       # one-shot workflow, attached
```

Re-run on demand:

```bash
docker compose run --rm client01
docker compose run --rm -e LOG_LEVEL=DEBUG client01
docker compose run --rm -e PASSWORD=wrong client01     # forces exit 2
```

## Expected log tail

```text
client01 | === client01 starting ===
client01 | Registered with QConnect: KeyId=qkey-...  (64-char hex key)
client01 | Authenticating via NAS http://radius-client:8082/auth as client01 (KeyId=qkey-...)
client01 | NAS auth OK for client01. Reply-Message='Welcome client01'
client01 | Generated QC (32 bytes)
client01 | TLS connection established to server01:8443 (cipher=('TLS_AES_256_GCM_SHA384','TLSv1.3',256))
client01 | Received QS (32 bytes)
client01 | Derived SessionKey (sha256, 32 bytes) - first 8 bytes: ...
client01 | Sent encrypted business message (19 bytes plaintext)
client01 | Decrypted server ack: b'ack: Hello from client01'
client01 | === client01 finished successfully ===
```

## Next steps

- **Real RNG:** replace `quantum.generate_quantum_random` with a real
  RNG/QRNG provider (HTTP API or hardware) — single function swap.
- **Proper TLS PKI:** issue `server01`'s cert from a lab CA, mount the CA
  into this image, set `TLS_VERIFY=true` + `TLS_CA_FILE=/app/ca.pem`.
- No change needed here when `radius01` policy starts enforcing the
  `Quantum-Key-Id` / `Quantum-Key` VSAs — they're already attached.

