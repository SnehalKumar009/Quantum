# RADIUS_CLIENT — NAS image source

This folder is the **image source** for the per-supplicant NAS
containers. In the active deployment it is built **twice** and run as
two distinct containers:

| Container              | Used by    | Image tag                                  | NAS-Identifier            |
| ---------------------- | ---------- | ------------------------------------------ | ------------------------- |
| `client-radiusclient`  | `client01` | `quantum-lab/client-radiusclient:latest`   | `client-radiusclient-01`  |
| `server-radiusclient`  | `server01` | `quantum-lab/server-radiusclient:latest`   | `server-radiusclient-01`  |

Both are defined inside the **CLIENT/** and **SERVER/** compose files
respectively, using `build: { context: ../RADIUS_CLIENT }`. There is no
shared NAS in the canonical deployment.

The standalone `docker-compose.yml` in this folder still works for
ad-hoc testing — it brings up a single instance called `radius-client`
publishing `tcp 8082` on the host.

## What the NAS does

Accepts an HTTP request from a supplicant and turns it into a RADIUS
Access-Request to `radius01`.

```text
POST /auth                       Authorization: Bearer lab-nas-token
{
  "username": "...",
  "password": "...",
  "KeyId":    "...",
  "Key":      "..."
}
->  200 {"ok": true,  "reply_message": "..."}
->  401 {"ok": false, "reason": "Access-Reject"}        or bad NAS token
->  502 RADIUS transport error
```

Plus `GET /healthz` for the docker healthcheck.

## Wire mapping (HTTP -> RADIUS)

| HTTP body field | RADIUS attribute              | Notes                                  |
| --------------- | ----------------------------- | -------------------------------------- |
| `username`      | `User-Name` (1)               | RFC 2865                               |
| `password`      | `User-Password` (2)           | obfuscated with shared secret          |
| `KeyId`         | `Quantum-Key-Id` (VSA 99999.1)| Vendor-specific                        |
| `Key`           | `Quantum-Key` (VSA 99999.2)   | Vendor-specific (hex string)           |
| (implicit)      | `NAS-Identifier` (32)         | `${NAS_IDENTIFIER}` env var            |

The two VSAs ride inside RADIUS attribute 26 (Vendor-Specific).
FreeRADIUS needs the matching dictionary to parse them — bundled in
`RADIUS/` as `dictionary.quantum-lab`.

## Configuration (env vars)

| Var                | Default                | |
| ------------------ | ---------------------- | -- |
| `RADIUS_HOST`      | `radius01`             | upstream RADIUS server |
| `RADIUS_AUTH_PORT` | `1812`                 | |
| `RADIUS_SECRET`    | `testing123`           | shared with `radius01` |
| `NAS_IDENTIFIER`   | `radius-client-01`     | overridden per instance |
| `NAS_SHARED_TOKEN` | `lab-nas-token`        | bearer expected from supplicants; empty disables |
| `LOG_LEVEL`        | `INFO`                 | |

## Curl examples

Hit the dedicated NASes from anywhere on `quantum-net`:

```bash
docker exec client01 curl -s -X POST http://client-radiusclient:8082/auth \
  -H "Authorization: Bearer lab-nas-token" \
  -H "Content-Type: application/json" \
  -d '{"username":"client01","password":"clientPassword",
       "KeyId":"qkey-abc","Key":"deadbeef"}'

docker exec server01 curl -s -X POST http://server-radiusclient:8082/auth \
  -H "Authorization: Bearer lab-nas-token" \
  -H "Content-Type: application/json" \
  -d '{"username":"server01","password":"serverPassword",
       "KeyId":"qkey-xyz","Key":"c0ffee"}'
```

Healthcheck:

```bash
docker exec client-radiusclient curl -s http://127.0.0.1:8082/healthz
```

## Standalone (ad-hoc) run

For one-off testing (single shared NAS published on host port 8082):

```bash
cd RADIUS_CLIENT
docker compose up --build
# then:
curl -s http://localhost:8082/healthz
```

