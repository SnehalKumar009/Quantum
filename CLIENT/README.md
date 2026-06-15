# CLIENT (client01) — one-shot TLS client + supplicant

Short-lived Python service. On boot it authenticates itself with
`radius01` via its dedicated NAS (`client-radiusclient`), then opens
a TLS connection to `server01:8443`, runs the per-connection
QKD-backed session-key exchange, sends one AES-GCM business message,
prints the decrypted ack, and exits.

## SAE identity

```text
SAE alias = sae-client01
SAE UUID  = 40a45fc8-687e-11f1-b7ff-525400b8fb7b
KME       = https://192.168.10.233:50555  (ETSI GS QKD 014, mTLS)
```

mTLS bundle is bind-mounted from
`${SAE_BUNDLE_DIR:-/home/agenticai/SNEHAL_POC}/sae-client01` to
`/etc/qkd:ro`.

## Layout

```text
CLIENT/
├── Dockerfile
├── docker-compose.yml          # mounts SAE bundle, sets QKD_* env
├── entrypoint.sh               # qkd-status boot probe + exec CMD
├── requirements.txt
├── README.md
└── app/
    ├── __init__.py
    ├── main.py                 # boot: enc_keys -> NAS auth -> TLS run -> exit
    ├── config.py               # dataclasses + env loading
    ├── qkd_client.py           # ETSI 014 client (with trace lines)
    ├── nas_auth.py             # POST /auth to client-radiusclient
    ├── tls_client.py           # opens TLS, runs QC enc_keys + QS dec_keys
    ├── crypto_session.py       # SHA-256 KDF + AES-GCM helpers
    ├── framing.py              # length-prefixed frames over TLS
    ├── quantum.py              # legacy os.urandom helper (kept for QC length constant)
    └── qconnect_client.py      # LEGACY (not imported by main.py)
```

## End-to-end flow

```text
entrypoint.sh
   ├── qkd-status boot probe against the KME
   └── exec python -m app.main

app.main.run()
   ├── own_sae_id(cfg.qkd)                                       # from /etc/qkd/sae-client01.info.json
   ├── enc_key(cfg.qkd, slave=cfg.qkd.peer_sae_id=sae-radius01)  # auth-plane enc_keys
   ├── (optional) sleep PRE_AUTH_DELAY_SECONDS                   # for manual failure tests
   ├── nas_auth.authenticate(... KeyId, MasterSaeId=self ...)    # POST http://client-radiusclient:8082/auth
   └── with tls_client.open_tls_connection(cfg.server) as tls:
           qc_bytes, qs_bytes = tls_client.exchange_quantum(tls, cfg.qkd)
           # exchange_quantum does:
           #   1. enc_key(slave=cfg.qkd.data_peer_sae_id=sae-server01) -> (kid_c, key_c)
           #   2. send  QC frame = "<own_sae>|<kid_c>"
           #   3. recv  QS frame = "<server_sae>|<kid_s>"
           #   4. dec_key(master=server_sae, kid_s)                    -> key_s
           #   5. return (key_c, key_s)
           SessionKey = SHA-256(qc_bytes || qs_bytes)
           send AES-GCM(SessionKey, "Hello from client01")
           recv AES-GCM(SessionKey, ack)                              # logs "ack: ..."
```

## Configuration (env vars)

| Variable | Default | Purpose |
| --- | --- | --- |
| `USERNAME` / `PASSWORD` | `client01` / `clientPassword` | Validated by FreeRADIUS `authorize`. |
| `NAS_URL` | `http://client-radiusclient:8082` | Dedicated NAS endpoint. |
| `NAS_SHARED_TOKEN` | `lab-nas-token` | Bearer for the NAS `/auth` call. |
| `NAS_HTTP_TIMEOUT` | `120` | Must exceed `PRE_AUTH_DELAY_SECONDS`. |
| `QKD_KME_URL` | `https://192.168.10.233:50555` | Real KME. |
| `QKD_SAE_ALIAS` / `QKD_PEER_SAE_ALIAS` | `sae-client01` / `sae-radius01` | Documentation-only; not used by code. |
| `QKD_CERT` / `QKD_KEY` / `QKD_CACERT` / `QKD_INFO_JSON` | `/etc/qkd/sae-client01.*` | mTLS bundle. |
| `QKD_PEER_SAE_ID` | `62391013-687d-11f1-b7ff-525400b8fb7b` | Auth-plane peer (= sae-radius01). |
| `QKD_DATA_PEER_SAE_ID` | **required** (= sae-server01 UUID, `4605150d-687e-11f1-b7ff-525400b8fb7b`) | Data-plane peer for the per-connection `enc_keys` call. |
| `SERVER_HOST` / `SERVER_PORT` | `server01` / `8443` | TLS target. |
| `TLS_VERIFY` / `TLS_CA_FILE` | `false` / unset | Lab mode skips cert verification (logs a WARNING). For production set `TLS_VERIFY=true` + `TLS_CA_FILE=<lab CA pem>`. |
| `PRE_AUTH_DELAY_SECONDS` | `60` | Pause between auth-plane `enc_keys` and the NAS auth call. Lets an operator tamper with / consume the key on the KME to observe Access-Reject. Set to `0` for production-like timing. |
| `LOG_LEVEL` | `INFO` | |

## Build & run

This is a one-shot service:

```bash
docker compose up --build      # blocks until client01 exits
```

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | All steps succeeded; ack decrypted. |
| 2 | NAS auth failed (Access-Reject or NAS transport error). |
| 3 | KME `enc_keys` for auth plane failed. |
| non-zero (other) | Uncaught exception inside the TLS/QKD exchange. |

## What you'll see in the logs

```text
=== client01 starting ===
client01 own SAE_ID (master) = 40a45fc8-687e-11f1-b7ff-525400b8fb7b
Requesting enc_keys from KME=... for peer (slave) SAE=62391013-...
[TRACE enc_key] REQ  master=self  slave=62391013-...  url=...
[TRACE enc_key] RESP body={'keys': [...]}
[TRACE enc_key] OK   key_id=qkey-...  key_b64=...
Got QKD key from qConnect: key_id=qkey-... (key withheld)
PRE_AUTH_DELAY_SECONDS=60.0 - sleeping ...
Authenticating via NAS http://client-radiusclient:8082/auth as client01 ...
NAS auth OK for client01. Reply-Message='Welcome client01'

TLS cert verification DISABLED (lab mode). ...
TLS connection established to server01:8443 (cipher=(...))
enc_keys: master=40a45fc8-... (self) slave=4605150d-... (server)
[TRACE enc_key] REQ ... slave=4605150d-...
[TRACE enc_key] OK  key_id=qkey-... key_b64=...
QC QKD key obtained: key_id=qkey-... len=32 (first 8B=...)
Sent QC frame (... bytes ASCII): 40a45fc8-...|qkey-...
QS frame parsed: master_sae_id=4605150d-... key_id=qkey-... -> calling dec_keys
[TRACE dec_key] REQ master=4605150d-... slave=self ...
[TRACE dec_key] OK  key_id=qkey-... key_b64=...
QS QKD key retrieved from KME: key_id=qkey-... len=32 (first 8B=...)
Both QKD halves in hand: QC=32 bytes  QS=32 bytes
Derived SessionKey (sha256, 32 bytes) - first 8 bytes: <X>   ← must match server01's
Sent encrypted business message (19 bytes plaintext)
Decrypted server ack: b'ack: Hello from client01'
=== client01 finished successfully ===
```

## Failure-mode test (key tampering / consumption)

With `PRE_AUTH_DELAY_SECONDS=60`, you have a 60-second window between
the boot-time `enc_keys` and the NAS auth call to break the auth path:

```bash
docker compose up -d --build radius01 client-radiusclient server-radiusclient server01
docker compose up --build client01
# While client01 is sleeping, cause the KME to refuse dec_keys on the
# issued KeyId (e.g. consume it from elsewhere). Expected:
docker logs client-radiusclient | grep -E 'Access-(Accept|Reject)'
#   Access-Reject for user=client01 reply_message='Quantum-Key dec_keys retrieval failed'
docker exec radius01 tail -n 40 /tmp/qkd-dec-key.log
```

## Legacy

- `app/qconnect_client.py` and `cfg.qconnect` are still defined but
  never called.
- `app/quantum.py` (`generate_quantum_random`) is no longer used in
  the SessionKey path; kept only for the `QRNG_BYTES = 32` constant.

