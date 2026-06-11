# radius-ui — Quantum Lab

Tiny FastAPI web UI for the lab's FreeRADIUS server. Open
[http://localhost:8081](http://localhost:8081) after the stack is up.

## What it does

- **Lists accounts** parsed from the live `authorize` file
  (`RADIUS/raddb/mods-config/files/authorize`, mounted read-only).
- **Test form** sends a real RADIUS Access-Request to `radius01:1812` and
  shows Access-Accept / Access-Reject plus the server's `Reply-Message`.
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

`radius01` (and ideally the rest of the stack) must be running so the
`quantum-net` Docker network exists:

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

- The UI does **not** edit accounts; FreeRADIUS reads them from the
  `authorize` file at startup. Edit that file and rebuild `radius01` to
  add/remove users.
- The UI itself uses RADIUS NAS-Identifier `radius-ui` (still covered by
  the broad `clients.conf` entry, secret `testing123`).

