# SERVER (server01) — TLS application server + supplicant

Long-running Python service. Plays two roles:

1. **Supplicant** at boot: authenticates itself with `radius01` via
   its dedicated NAS (`server-radiusclient`), using a fresh QKD key
   obtained from the real qConnect KME.
2. **TLS application listener** on `:8443`: accepts connections from
   `client01` and runs a per-connection QKD-backed session-key
   exchange before exchanging an AES-GCM business message.

## SAE identity

```text
SAE alias = sae-server01
SAE UUID  = 4605150d-687e-11f1-b7ff-525400b8fb7b
KME       = https://192.168.10.233:50555  (ETSI GS QKD 014, mTLS)
```

mTLS bundle is bind-mounted from
`${SAE_BUNDLE_DIR:-/home/agenticai/SNEHAL_POC}/sae-server01` to
`/etc/qkd:ro`.

## Layout

```text
SERVER/
├── Dockerfile
├── docker-compose.yml          # mounts SAE bundle, sets QKD_* env, healthcheck
├── entrypoint.sh               # self-signs TLS cert + qkd-status boot probe + exec CMD
├── requirements.txt
├── README.md
└── app/
    ├── __init__.py
    ├── main.py                 # boot: enc_keys -> NAS auth -> serve_forever
    ├── config.py               # dataclasses + env loading
    ├── qkd_client.py           # ETSI 014 client (own_sae_id / enc_key / dec_key) with trace lines
    ├── nas_auth.py             # POST /auth to server-radiusclient
    ├── tls_server.py           # per-connection QC/QS QKD exchange + AES-GCM I/O
    ├── crypto_session.py       # SHA-256 KDF + AES-GCM helpers
    ├── framing.py              # length-prefixed frames over TLS
    ├── quantum.py              # legacy os.urandom helper (kept for QC length constant)
    └── qconnect_client.py      # LEGACY (not imported by main.py)
```

## Boot-time flow

```text
entrypoint.sh
   ├── generate self-signed cert at $CERT_DIR/server.{crt,key} (first boot)
   ├── qkd-status boot probe against the KME
   └── exec python -m app.main

app.main.run()
   ├── own_sae_id(cfg.qkd)                                       # from /etc/qkd/sae-server01.info.json
   ├── enc_key(cfg.qkd, slave=cfg.qkd.peer_sae_id=sae-radius01)  # ETSI 014 enc_keys (mTLS)
   ├── nas_auth.authenticate(... KeyId, MasterSaeId=self ...)    # POST http://server-radiusclient:8082/auth
   └── tls_server.serve_forever(cfg.listener, cfg.qkd)           # listen on :8443
```

## Per-connection flow (data plane)

`tls_server._handle_connection` per accepted TLS socket:

```text
1. recv frame 1 (QC = "<client_sae_id>|<key_id_c>")
2. dec_key(master=client_sae_id, key_id_c) ->  key_c  (QC bytes)
   - optional pin: reject if QKD_DATA_PEER_SAE_ID is set and != client_sae_id
3. enc_key(slave=client_sae_id)           ->  (key_id_s, key_s)
   - the client SAE was just learned dynamically from the QC frame
4. send frame 2 (QS = "<own_sae>|<key_id_s>")
5. SessionKey = SHA-256(key_c || key_s)
6. recv frame 3:  nonce(12) || AES-GCM ciphertext   -> decrypt
7. send frame 4:  AES-GCM("ack: " + plaintext)
```

## Configuration (env vars)

| Variable | Default | Purpose |
| --- | --- | --- |
| `USERNAME` / `PASSWORD` | `server01` / `serverPassword` | Validated by FreeRADIUS `authorize`. |
| `NAS_URL` | `http://server-radiusclient:8082` | Dedicated NAS endpoint. |
| `NAS_SHARED_TOKEN` | `lab-nas-token` | Bearer for the NAS `/auth` call. |
| `QKD_KME_URL` | `https://192.168.10.233:50555` | Real KME. |
| `QKD_SAE_ALIAS` | `sae-server01` | Documentation-only; not used by code. |
| `QKD_CERT` / `QKD_KEY` / `QKD_CACERT` / `QKD_INFO_JSON` | `/etc/qkd/sae-server01.*` | mTLS bundle (read-only mount). |
| `QKD_PEER_SAE_ID` | `62391013-687d-11f1-b7ff-525400b8fb7b` | Auth-plane peer (= sae-radius01). |
| `QKD_DATA_PEER_SAE_ID` | (set to `sae-client01` UUID, **optional pin**) | If non-empty, server only accepts TLS connections whose QC frame names this exact client SAE. If empty, it accepts whoever connects. |
| `LISTEN_HOST` / `LISTEN_PORT` | `0.0.0.0` / `8443` | TLS listener. |
| `CERT_DIR` / `CERT_CN` | `/app/certs` / `server01` | Self-signed cert generation. |
| `LOG_LEVEL` | `INFO` | |

## Build & run

```bash
docker compose up --build
```

Healthcheck pings `127.0.0.1:8443` so dependent services
(`client01`) can `depends_on: condition: service_healthy`.

## What you'll see in the logs

Each accepted TLS connection produces (look for `server01.conn.<peer>`):

```text
Accepted TLS connection from ('…', …)
QC frame parsed: master_sae_id=<sae-client01> key_id=qkey-… -> calling dec_keys
[TRACE dec_key] REQ  master=<sae-client01>  slave=self  …
[TRACE dec_key] RESP body={'keys': [...]}
[TRACE dec_key] OK   key_id=qkey-…  key_b64=…
QC QKD key retrieved: key_id=qkey-… len=32 (first 8B=…)
enc_keys: master=<sae-server01> (self) slave=<sae-client01> (client, learned from QC)
[TRACE enc_key] REQ  master=self  slave=<sae-client01>  …
[TRACE enc_key] RESP body={'keys': [...]}
[TRACE enc_key] OK   key_id=qkey-…  key_b64=…
QS QKD key obtained: key_id=qkey-… len=32 (first 8B=…)
Sent QS frame (… bytes ASCII): <sae-server01>|qkey-…
Derived SessionKey first 8 bytes: <X>      ← must match client01's
Decrypted message from client: b'Hello from client01'
Sent encrypted ack (… bytes ciphertext)
```

## Legacy

- `app/qconnect_client.py` and `cfg.qconnect` are still defined but
  never called. They reference the deprecated local `QConnect/` stub —
  safe to remove when that folder is cleaned up.
- `app/quantum.py` (`generate_quantum_random`) is no longer used in
  the SessionKey path; kept only for the `QRNG_BYTES = 32` constant.

