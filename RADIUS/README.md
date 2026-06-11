# RADIUS (radius01) — Quantum Secure Lab

FreeRADIUS 3.x server providing **Authentication, Authorization, and
Accounting (AAA)**. In the current architecture all auth requests arrive
from a single NAS (`radius-client`) — supplicants (`client01`,
`server01`) never speak RADIUS directly.

## Layout

```text
RADIUS/
├── Dockerfile
├── docker-compose.yml
├── README.md
├── .dockerignore
├── scripts/
│   └── qconnect-fetch.sh                   # helper: curl QConnect, append to keys file
└── raddb/
    ├── clients.conf                        # NAS allow-list + shared secret
    ├── dictionary.quantum-lab              # Quantum-Lab vendor (99999) VSAs
    └── mods-config/
        └── files/
            ├── authorize                   # user accounts (client01, server01, testuser)
            └── keys                        # QConnect-issued key-id / key pairs
```

Only the files we *override* live in `raddb/`. Everything else is
inherited from the official `freeradius/freeradius-server:3.2.5` image.

## Initial accounts

| Username   | Password         | Notes                              |
| ---------- | ---------------- | ---------------------------------- |
| `client01` | `clientPassword` | App client identity                |
| `server01` | `serverPassword` | App server identity                |
| `testuser` | `testpw`         | Convenience account for `radtest`  |

Shared secret (all NASes): **`testing123`**.

## Vendor-Specific Attributes (Quantum-Lab)

`raddb/dictionary.quantum-lab` defines vendor ID **99999** with:

| Attr # | Name              | Type   | Used for                            |
| ------ | ----------------- | ------ | ----------------------------------- |
| 1      | `Quantum-Key-Id`  | string | QConnect KeyId from supplicant      |
| 2      | `Quantum-Key`     | string | QConnect Key (hex) from supplicant  |

These attributes ride inside RADIUS attribute 26 (Vendor-Specific). The
Dockerfile appends `$INCLUDE dictionary.quantum-lab` to
`/etc/raddb/dictionary`, so FreeRADIUS parses + logs them. Policy
enforcement using these VSAs is **not yet wired** — they are transported
end-to-end but currently ignored by `authorize`.

## clients.conf

First-match-wins. Order:

1. `radius-client` — the dedicated NAS (`shortname = radius-client-01`).
2. `localhost` — for `radtest` from inside the container.
3. `docker-network` — broad fallback for `172.16.0.0/12`.

All entries share the same secret `testing123`.

## qconnect-fetch helper

Bundled inside the image at `/usr/local/bin/qconnect-fetch`. Calls
QConnect and appends the returned key-id/key into
`/etc/raddb/mods-config/files/keys` in the same line format as
`authorize`:

```text
qkey-3f8a91b2c0de    Cleartext-Password := "0a1b2c...ef"
```

Usage from the host:

```bash
docker exec radius01 qconnect-fetch                       # new key
docker exec radius01 qconnect-fetch qkey-3f8a91b2c0de     # fetch existing by ID
docker exec radius01 cat /etc/raddb/mods-config/files/keys
```

Idempotent: already-present KeyIds are not re-appended.

## Build & run

```bash
docker compose up --build      # standalone, debug mode (-X)
```

Container is published as `udp/1812` (auth) and `udp/1813` (accounting).

## Smoke tests

Indirect (the real path, through the NAS):

```bash
curl -s -X POST http://localhost:8082/auth \
  -H "Authorization: Bearer lab-nas-token" \
  -H "Content-Type: application/json" \
  -d '{"username":"client01","password":"clientPassword",
       "KeyId":"qkey-test","Key":"deadbeef"}' | jq
# -> {"ok":true,"reply_message":"Welcome client01",...}
```

Direct RADIUS (from `localhost` or a container on `quantum-net`):

```bash
docker run --rm --network quantum-net freeradius/freeradius-server:3.2.5 \
    radtest client01 clientPassword radius01 0 testing123
# -> Received Access-Accept
```

## Switching to quieter logging

Edit the `CMD` in `Dockerfile`:

```dockerfile
CMD ["radiusd", "-f"]   # foreground, normal logging (no -X debug spam)
```

## Next steps

- Author a FreeRADIUS policy that **uses** `Quantum-Key-Id` /
  `Quantum-Key` (e.g. cross-check with QConnect at auth time).
- Tighten `clients.conf` to only the `radius-client` container IP.
- Use a real Private Enterprise Number instead of vendor 99999.

