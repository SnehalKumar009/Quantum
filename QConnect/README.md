# QConnect — RNG / key-distribution service

A small FastAPI service that stands in for the lab's RNG product.
Generates `KeyId`/`Key` pairs, persists each one as a file inside the
container (backed by a Docker named volume), and serves them by ID over
HTTP.

In the current architecture, **`client01` and `server01` register
themselves with QConnect on boot** to obtain the `(KeyId, Key)` they
include in their authentication request to the NAS. Anyone else on the
lab network (including `radius01` via the `qconnect-fetch` helper) can
also generate or look up keys.

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
- `Key`   — `KEY_BYTES` (default 32) random bytes, hex-encoded -> 64 chars.

`GET /keys` intentionally omits the secret material:

```json
{ "count": 3, "keys": ["qkey-3f8a91b2c0de", "qkey-771caaff1100", "..."] }
```

## Storage

One file per key under `/data/keys/<KeyId>.json`, persisted via the
`qconnect-data` Docker named volume. Survives container restarts and
rebuilds. To wipe all keys:

```bash
docker compose down -v   # also removes named volumes
```

To inspect the underlying files on the Ubuntu host:

```bash
docker volume inspect quantum-lab_qconnect-data --format '{{ .Mountpoint }}'
sudo ls -la /var/lib/docker/volumes/quantum-lab_qconnect-data/_data
```

## Configuration (env vars)

| Variable             | Default       | Description                          |
| -------------------- | ------------- | ------------------------------------ |
| `QCONNECT_DATA_DIR`  | `/data/keys`  | Where key files are stored           |
| `KEY_BYTES`          | `32`          | Raw key length before hex encoding   |
| `LOG_LEVEL`          | `INFO`        |                                      |

## Examples

From the Ubuntu host:

```bash
curl -s -X POST http://localhost:9000/keys/generate | jq
curl -s http://localhost:9000/keys/qkey-3f8a91b2c0de | jq
curl -s http://localhost:9000/keys | jq
```

From inside any lab container (no port mapping involved):

```bash
docker exec radius01 curl -s -X POST http://qconnect:9000/keys/generate
docker exec server01 curl -s http://qconnect:9000/healthz
```

From `radius01` with auto-append to the keys file:

```bash
docker exec radius01 qconnect-fetch
```

## Standalone run

`quantum-net` must already exist (created by `RADIUS/docker-compose.yml`
or the top-level compose). Then:

```bash
cd QConnect
docker compose up --build
```

## Notes

- No auth on the API today. For production a shared bearer token would
  go in front of every endpoint (mirrors what `radius-client` does).
- The default RNG is `secrets.token_hex` (OS CSPRNG). When the real RNG
  product is wired in, only `_new_key_hex()` in `app/main.py` changes.

