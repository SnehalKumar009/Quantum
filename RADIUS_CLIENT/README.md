# radius-client (NAS) — Quantum Secure Lab

The NAS that sits between supplicants (`client01`, `server01`) and the
RADIUS server (`radius01`). Supplicants speak HTTP; the NAS speaks RADIUS.

## Endpoint

```
POST /auth                Authorization: Bearer lab-nas-token
{ "username": "...", "password": "...", "KeyId": "...", "Key": "..." }

200 {"ok": true,  "reply_message": "..."}
401 {"ok": false, "reason": "Access-Reject"}    or invalid NAS token
502 {detail: "RADIUS transport error: ..."}
```

Plus `GET /healthz`.

## Wire mapping (HTTP → RADIUS)

| HTTP body field | RADIUS attribute             | Notes                          |
| --------------- | ---------------------------- | ------------------------------ |
| `username`      | `User-Name` (1)              | RFC 2865                       |
| `password`      | `User-Password` (2)          | obfuscated with shared secret  |
| `KeyId`         | `Quantum-Key-Id` (VSA 99999.1) | string                        |
| `Key`           | `Quantum-Key` (VSA 99999.2)    | hex-encoded string            |
| (implicit)      | `NAS-Identifier` = `radius-client-01` |                       |

The two VSAs ride inside RADIUS attribute 26 (Vendor-Specific). FreeRADIUS
needs the matching dictionary to parse them — bundled in `RADIUS/` as
`dictionary.quantum-lab`.

## Configuration (env)

| Var | Default | |
|---|---|---|
| `RADIUS_HOST` | `radius01` | upstream RADIUS server |
| `RADIUS_AUTH_PORT` | `1812` | |
| `RADIUS_SECRET` | `testing123` | shared with `radius01` |
| `NAS_IDENTIFIER` | `radius-client-01` | what `radius01` logs as `Called-Station-Id`-like ID |
| `NAS_SHARED_TOKEN` | `lab-nas-token` | bearer token expected from supplicants; empty disables |
| `LOG_LEVEL` | `INFO` | |

## Curl example

```bash
curl -s -X POST http://localhost:8082/auth \
  -H "Authorization: Bearer lab-nas-token" \
  -H "Content-Type: application/json" \
  -d '{"username":"client01","password":"clientPassword",
       "KeyId":"qkey-abcdef012345","Key":"0a1b2c..."}' | jq
```

