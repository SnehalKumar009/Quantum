# radius-ui — Quantum Lab

Tiny FastAPI web UI for the lab's FreeRADIUS server. Open
[http://localhost:8081](http://localhost:8081) after the stack is up.

> **Note:** this UI talks **directly** to `radius01` over RADIUS — it
> *does not* go through the `radius-client` NAS. That's intentional: it
> is a sanity tool to confirm the RADIUS server is alive and the user
> file is correct. To exercise the real auth path used by `client01` /
> `server01`, hit `radius-client` directly (see
> [`../RADIUS_CLIENT/README.md`](../RADIUS_CLIENT/README.md)).

## What it does

- **Lists accounts** parsed from the live `authorize` file
  (`RADIUS/raddb/mods-config/files/authorize`, mounted read-only).
- **Test form** sends a real RADIUS Access-Request to `radius01:1812`
  and shows Access-Accept / Access-Reject plus the server's
  `Reply-Message`.
- `/healthz` JSON endpoint for liveness checks.

## Layout

```text
RADIUS_UI/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .dockerignore
├── README.md
└── app/
    ├── __init__.py
    ├── main.py
    ├── radius_dictionary
    └── templates/
        └── index.html
```

## Prerequisites

`radius01` must be running (it owns the `quantum-net` Docker network):

```bash
cd ..
docker compose up -d --build radius01
```

## Run standalone

```bash
cd RADIUS_UI
docker compose up --build
```

Then browse to `http://localhost:8081`.

## Configuration (env vars)

| Variable           | Default                                           |
| ------------------ | ------------------------------------------------- |
| `RADIUS_HOST`      | `radius01`                                        |
| `RADIUS_AUTH_PORT` | `1812`                                            |
| `RADIUS_SECRET`    | `testing123`                                      |
| `AUTHORIZE_FILE`   | `/raddb/mods-config/files/authorize` (mounted RO) |

## Notes

- The UI does **not** edit accounts. To add users, edit
  `RADIUS/raddb/mods-config/files/authorize` and rebuild `radius01`.
- Its requests reach `radius01` from inside the `quantum-net` subnet and
  are matched by the broad `docker-network` entry in `clients.conf`
  (secret `testing123`). It does not impersonate `radius-client`.

