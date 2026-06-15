# RADIUS_CLIENT — per-supplicant NAS (FastAPI + pyrad)

A small FastAPI service that acts as a **Network Access Server (NAS)**
in RADIUS terms: it accepts an HTTP `/auth` POST from a supplicant
(`client01` or `server01`) and turns it into a RADIUS Access-Request
to `radius01`, including the Quantum-Lab VSAs.

A single image is built once and run as **two containers** —
`client-radiusclient` and `server-radiusclient` — so each supplicant
has its own dedicated NAS with a distinct `NAS-Identifier`.

## What it does

```
supplicant ── POST /auth (Bearer lab-nas-token) ──►  this NAS
   {                                                    │
     "username":    "client01",                         │ build RADIUS
     "password":    "clientPassword",                   │ Access-Request
     "KeyId":       "<UUID from KME enc_keys>",         │ with PAP
     "MasterSaeId": "<own SAE UUID>"                    │ + VSAs
   }                                                    ▼
                                              radius01:1812 (UDP)
                                                        │
                                              quantum_key_check
                                              -> mTLS dec_keys at KME
                                                        │
                                              Accept / Reject
                                                        │
   ◄────────  200 / 401  ◄──────────────────────────────┘
```

Endpoints:

| Method | Path | Auth | Body / Response |
| --- | --- | --- | --- |
| POST | `/auth` | `Authorization: Bearer <NAS_SHARED_TOKEN>` | See above. 200 on Access-Accept, 401 on Access-Reject, 502 on transport / DNS error. |
| GET | `/healthz` | none | `{ "status":"ok", "radius_target":"radius01:1812", "nas_identifier":"…", "token_required": true }` |

## RADIUS attribute mapping

| HTTP field | RADIUS attribute | Notes |
| --- | --- | --- |
| `username` | `User-Name` | |
| `password` | `User-Password` | PwCrypt-encoded with the shared RADIUS secret. |
| `KeyId` | `Quantum-Key-Id` (vendor 99999, attr 1) | UUID from a prior `enc_keys` on the supplicant's SAE. |
| `MasterSaeId` | `Quantum-Master-SAE-ID` (vendor 99999, attr 3) | UUID of the SAE that called `enc_keys`. |
| (constant) | `NAS-Identifier` | `client-radiusclient-01` or `server-radiusclient-01`. |

The Quantum-Lab VSAs are defined in `app/radius_dictionary` (loaded by
pyrad at process start) and in
`RADIUS/raddb/dictionary.quantum-lab` (loaded by FreeRADIUS).

## Layout

```text
RADIUS_CLIENT/
├── Dockerfile
├── docker-compose.yml          # client-radiusclient + server-radiusclient
├── requirements.txt
├── README.md
└── app/
    ├── __init__.py
    ├── main.py                 # FastAPI + pyrad client
    └── radius_dictionary       # standalone vendor dict for pyrad
```

## Configuration (env vars, per container)

| Variable | Default | Purpose |
| --- | --- | --- |
| `RADIUS_HOST` | `radius01` | UDP target. |
| `RADIUS_AUTH_PORT` | `1812` | |
| `RADIUS_SECRET` | `testing123` | RFC 2865 shared secret. Must match `RADIUS/raddb/clients.conf`. |
| `NAS_IDENTIFIER` | per service (`client-radiusclient-01` / `server-radiusclient-01`) | Logged by FreeRADIUS so each NAS is distinguishable in `radiusd -X` output. |
| `NAS_SHARED_TOKEN` | `lab-nas-token` | Bearer token expected on `/auth`. Empty disables the check. |
| `LOG_LEVEL` | `INFO` | |

The two services share **all** of the above except `container_name`,
`hostname`, and `NAS_IDENTIFIER`.

## Build & run

Standalone (just the NAS layer):

```bash
docker compose up --build
```

The two containers each expose `8082` internally on `quantum-net`;
neither is published to the host by default — `client01` / `server01`
hit them by service name (`http://client-radiusclient:8082` etc.).

Healthcheck (`GET /healthz`) is wired in `docker-compose.yml` so the
supplicant compose files can `depends_on: condition: service_healthy`.

## Smoke test

```bash
# 1. Get a fresh key from a supplicant's SAE (here, sae-client01):
docker exec client01 python -c "from app.config import load_config; from app.qkd_client import enc_key, own_sae_id; cfg=load_config().qkd; sae=own_sae_id(cfg); k=enc_key(cfg, cfg.peer_sae_id); print(sae, k.key_id)"
#   -> 40a45fc8-687e-11f1-b7ff-525400b8fb7b  qkey-<...>

# 2. Hit the NAS directly:
curl -s -X POST http://localhost:8082/auth \
  -H "Authorization: Bearer lab-nas-token" \
  -H "Content-Type: application/json" \
  -d '{"username":"client01","password":"clientPassword",
       "KeyId":"qkey-<...>","MasterSaeId":"40a45fc8-687e-11f1-b7ff-525400b8fb7b"}' | jq
# -> {"ok":true,"reply_message":"Welcome client01","reason":""}
```

(The NAS containers don't expose port 8082 to the host by default —
to run the curl above you'd add a `ports: ["8082:8082"]` mapping or
`docker exec` from inside another container on `quantum-net`.)

## Failure modes

| HTTP | Cause |
| --- | --- |
| 401 | Bad / missing `Authorization: Bearer …` header. |
| 401 | RADIUS returned Access-Reject. `detail` carries `reply_message` + `reason`. |
| 502 | Cannot resolve `RADIUS_HOST` or UDP transport error. |
| 422 | Pydantic validation: missing/empty `username` / `password` / `KeyId` / `MasterSaeId`. |

