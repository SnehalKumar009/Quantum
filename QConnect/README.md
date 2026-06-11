# QConnect — simulated RNG / key-distribution service

A small FastAPI service that stands in for the new RNG product. Generates
key-id/key pairs, persists each one as a file inside the container, and
serves them by ID over HTTP.

## API

| Method | Path                 | Description                              |
| ------ | -------------------- | ---------------------------------------- |
| POST   | `/keys/generate`     | Generate + persist a new key pair        |
| GET    | `/keys`              | List all stored KeyIds                   |
| GET    | `/keys/{key_id}`     | Fetch a previously generated key         |
| DELETE | `/keys/{key_id}`     | Remove a key                             |
| GET    | `/healthz`           | Liveness probe                           |
| GET    | `/docs`              | Swagger UI (FastAPI auto-generated)      |

All key-bearing responses use this shape:

```json
{ "KeyId": "qkey-3f8a91b2c0de", "Key": "0a1b...<64 hex chars>...ef" }
```

- `KeyId` — `qkey-` + 12 hex chars from a UUID4.
- `Key` — `KEY_BYTES` (default 32) random bytes, hex-encoded ⇒ 64 chars.

## Storage

One file per key under `/data/keys/<KeyId>.json`, persisted via the
`qconnect-data` Docker volume. Survives container restarts/rebuilds.

To wipe all keys:

```bash
docker compose down -v   # nukes named volumes too
```

## Configuration (env vars)

| Variable             | Default       | Description                          |
| -------------------- | ------------- | ------------------------------------ |
| `QCONNECT_DATA_DIR`  | `/data/keys`  | Where key files are stored           |
| `KEY_BYTES`          | `32`          | Raw key length before hex encoding   |
| `LOG_LEVEL`          | `INFO`        |                                      |

## Examples

Generate a new key:

```bash
curl -s -X POST http://localhost:9000/keys/generate | jq
# {
#   "KeyId": "qkey-3f8a91b2c0de",
#   "Key":   "0a1b2c...ef"
# }
```

Fetch it later:

```bash
curl -s http://localhost:9000/keys/qkey-3f8a91b2c0de | jq
```

List everything:

```bash
curl -s http://localhost:9000/keys | jq
```

From inside another lab container (e.g. `radius01`, `server01`, `client01`)
just use the hostname `qconnect`:

```bash
curl -s -X POST http://qconnect:9000/keys/generate
curl -s http://qconnect:9000/keys/qkey-3f8a91b2c0de
```

## Standalone run

`quantum-net` must already exist (created by `RADIUS/docker-compose.yml` or
the top-level compose). Then:

```bash
cd QConnect
docker compose up --build
```

