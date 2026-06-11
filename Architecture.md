# Quantum Secure Client/Server Lab — Architecture Design

## Goal

Build a secure client/server system that combines four independent
security layers:

- **AAA** via RADIUS, with **per-supplicant NAS** (Network Access Server)
  instances mediating between each supplicant and the RADIUS server.
- **TLS** for transport security between the application client and
  application server.
- **RNG / key distribution** via a central service (**QConnect**) that
  issues `(KeyId, Key)` pairs which supplicants attach to their auth
  requests.
- A **Quantum Random Exchange** at the application layer that derives a
  session key independent of TLS keying material.

Runs as Docker containers on a single Ubuntu host, designed so the same
images can later be split across multiple hosts.

---

## High-level architecture

```text
                          +--------------+
                          |   QConnect   |   (HTTP key store)
                          +-------+------+
                                  | POST /keys/generate    GET /keys/{id}
              +-------------------+-------------------+
              v                                       v
   +----------+    POST /auth    +----------------------+    RADIUS UDP   +------------+
   | client01 |----------------->| client-radiusclient  |---------------->|            |
   +----------+                  +----------------------+                 |  radius01  |
                                                                          | FreeRADIUS |
   +----------+    POST /auth    +----------------------+    RADIUS UDP   |            |
   | server01 |----------------->| server-radiusclient  |---------------->|            |
   +----+-----+                  +----------------------+                 +------------+
        |                                                                       ^
        |                                                              browser  |
        |              +-----------+                                   UI tests |
        |              | radius-ui |------------------------------------------+
        |              +-----------+
        |
        |   --- TLS 1.3 --->   +----------+
        +--------------------> | server01 |   per-conn: QC/QS exchange,
                               +----------+   SHA-256 key derive,
                                              AES-GCM payload.
```

Each supplicant owns its own NAS. Both NASes are instances of the same
image built from `RADIUS_CLIENT/`. They differ only in `container_name`,
`hostname`, and `NAS_IDENTIFIER`.

---

## Components

| Component                | Role                                          | Container               | Exposed |
| ------------------------ | --------------------------------------------- | ----------------------- | ------- |
| RADIUS server            | AAA — validates username/password             | `radius01`              | udp 1812/1813 |
| NAS for client           | HTTP→RADIUS proxy for client01                | `client-radiusclient`   | (internal 8082) |
| NAS for server           | HTTP→RADIUS proxy for server01                | `server-radiusclient`   | (internal 8082) |
| App client (supplicant)  | One-shot workflow                             | `client01`              | – |
| App server (supplicant)  | Long-lived TLS listener                       | `server01`              | tcp 8443 |
| Key service              | Issues `(KeyId, Key)` pairs                   | `qconnect`              | tcp 9000 |
| RADIUS UI                | Browser tool to test RADIUS directly          | `radius-ui`             | tcp 8081 |

All attach to one Docker bridge network: **`quantum-net`**.

---

## Identities & secrets

| Account / secret      | Value             | Owner / consumers                  |
| --------------------- | ----------------- | ---------------------------------- |
| `client01`            | `clientPassword`  | RADIUS user (supplicant identity)  |
| `server01`            | `serverPassword`  | RADIUS user (supplicant identity)  |
| `testuser`            | `testpw`          | Smoke-test account                 |
| RADIUS shared secret  | `testing123`      | every NAS <-> `radius01`           |
| NAS bearer token      | `lab-nas-token`   | supplicants <-> their NAS          |

Supplicants **do not** know the RADIUS shared secret. Each NAS owns it.

---

## RADIUS attributes on the wire

Standard RFC 2865:

| #  | Name             | Source                                            |
| -- | ---------------- | ------------------------------------------------- |
| 1  | `User-Name`      | supplicant                                        |
| 2  | `User-Password`  | supplicant (encrypted by NAS with shared secret)  |
| 32 | `NAS-Identifier` | NAS (`client-radiusclient-01` or `server-radiusclient-01`) |

Vendor-Specific Attributes (Quantum-Lab, vendor ID **`99999`**), defined
in `RADIUS/raddb/dictionary.quantum-lab`:

| # | Name             | Type   | Source                            |
| - | ---------------- | ------ | --------------------------------- |
| 1 | `Quantum-Key-Id` | string | supplicant (from QConnect)        |
| 2 | `Quantum-Key`    | string | supplicant (from QConnect, hex)   |

`radius01` parses and logs the VSAs today; policy enforcement on them is
the next planned change.

---

## Boot flow per supplicant

```text
+----------------------------- client01 / server01 -----------------------------+
|                                                                              |
|  1.  POST {QCONNECT_URL}/keys/generate                                       |
|      <--- {"KeyId":"qkey-...", "Key":"<64 hex>"}                             |
|                                                                              |
|  2.  POST {NAS_URL}/auth                                                     |
|           Authorization: Bearer lab-nas-token                                |
|           {"username","password","KeyId","Key"}                              |
|      <--- 200 {"ok": true,  "reply_message": "..."}     (or 401 -> exit 2)   |
|                                                                              |
|  3.  (server01 only) listen on 0.0.0.0:8443                                  |
|      (client01)      proceed to TLS exchange                                 |
+------------------------------------------------------------------------------+
                                  |
                                  v
+---- client01 NAS_URL = http://client-radiusclient:8082 ----------------------+
+---- server01 NAS_URL = http://server-radiusclient:8082 ----------------------+
|                                                                              |
|  Build Access-Request:                                                       |
|     User-Name      = username                                                |
|     User-Password  = PwCrypt(password)                                       |
|     Quantum-Key-Id = KeyId        (VSA 99999.1)                              |
|     Quantum-Key    = Key          (VSA 99999.2)                              |
|     NAS-Identifier = client-radiusclient-01  OR  server-radiusclient-01      |
|                                                                              |
|  Send UDP to radius01:1812                                                   |
|  Map Access-Accept -> 200 OK ; Access-Reject -> 401                          |
+------------------------------------------------------------------------------+
                                  |
                                  v
+--------------------------------- radius01 -----------------------------------+
|                                                                              |
|  files module: look up User-Name in `authorize`,                             |
|                compare User-Password to stored cleartext.                    |
|  VSAs logged but ignored (today).                                            |
|  Logs identify the NAS by its `shortname` from clients.conf.                 |
+------------------------------------------------------------------------------+
```

---

## Application flow (after auth)

After both supplicants have authenticated through their respective NASes,
`client01` connects to `server01` over TLS:

```text
client01                                              server01
    |   TCP + TLS 1.3 handshake (server cert self-signed, lab mode)
    | ------------------------------------------------>
    |
    |  frame(QC, 32 bytes)         ----------------->
    |  <------------- frame(QS, 32 bytes)
    |
    |            SessionKey = SHA-256(QC || QS)
    |
    |  frame( nonce(12) || AES-GCM(plaintext) ) ---->
    |  <----- frame( nonce(12) || AES-GCM("ack: "+pt) )
    |
    |  TLS shutdown
```

---

## Network & ports

| Listener                | Container               | Host port (default) |
| ----------------------- | ----------------------- | ------------------- |
| RADIUS auth             | `radius01`              | udp 1812            |
| RADIUS acct             | `radius01`              | udp 1813            |
| TLS app                 | `server01`              | tcp 8443            |
| QConnect HTTP           | `qconnect`              | tcp 9000            |
| RADIUS UI HTTP          | `radius-ui`             | tcp 8081            |
| client NAS HTTP         | `client-radiusclient`   | (internal only)     |
| server NAS HTTP         | `server-radiusclient`   | (internal only)     |

All inter-container traffic flows over the Docker bridge `quantum-net`
using container hostnames (no port mapping needed inside the network).

---

## Startup ordering (top-level compose)

```text
radius01  --+
qconnect  --+--  (no dependencies)
            |
            v
client-radiusclient  (depends_on: radius01)     -- healthcheck: GET /healthz
server-radiusclient  (depends_on: radius01)     -- healthcheck: GET /healthz
            |
            v
server01   (depends_on: qconnect started, server-radiusclient healthy)
            |                                   -- healthcheck: TCP :8443
            v
client01   (depends_on: qconnect started, client-radiusclient healthy,
                         server01 healthy)
```

`radius-ui` only depends on `radius01`.

---

## Design principles

| Principle | How it's realised |
| --------- | ----------------- |
| **Separation of concerns** | RADIUS = identity. TLS = transport. QConnect = key material. Quantum exchange = session key. |
| **Per-supplicant NAS** | Mirrors real deployments where each access edge holds its own RADIUS-secret-bearing NAS. Smaller blast radius if one is compromised. |
| **Supplicants stay small** | They speak only HTTP (to their NAS + QConnect) and TLS (to peer). They never carry the RADIUS shared secret. |
| **Config from env** | Every host/port/secret comes from environment variables -> same image runs on one host or many. |
| **Cryptographic defence in depth** | Even if TLS were broken, payloads are still AES-GCM with a key only the two peers share. |
| **Future-proof on the wire** | `Quantum-Key-Id` / `Quantum-Key` already ride in every Access-Request; only `radius01` policy needs to change to start enforcing them. |

---

## Phase status

| Phase | Description | Status |
| ----- | ----------- | ------ |
| 1  | Single-host Docker lab on `quantum-net` | DONE |
| 2  | TLS between `client01` <-> `server01` (self-signed, lab mode) | DONE |
| 3  | RADIUS auth via per-supplicant NAS | DONE |
| 3b | QConnect key issuance + transport as VSAs | DONE — issued + forwarded (RADIUS policy TODO) |
| 4  | Quantum random exchange | DONE — protocol live; RNG is placeholder `os.urandom`, awaiting real RNG product |
| 5  | `SessionKey = SHA-256(QC || QS)` | DONE |
| 6  | AES-GCM business payloads inside TLS | DONE |
| —  | Multi-host deployment | pending — no code change needed; just env-var hostnames |
| —  | Lab CA + verified TLS / mTLS | pending |
| —  | RADIUS Accounting (`Acct-Start/Stop`) | pending |
| —  | FreeRADIUS policy that enforces VSAs | pending |
| —  | Real RNG product wired into `quantum.py` | pending |

---

## Future multi-machine deployment

```text
Ubuntu Machine A           Ubuntu Machine B                Ubuntu Machine C
+- client01                +- server01                     +- radius01
+- client-radiusclient     +- server-radiusclient          +- qconnect
                                                           +- radius-ui
```

Same Docker images, different `NAS_URL`, `QCONNECT_URL`, `SERVER_HOST`,
`RADIUS_HOST` env vars. Tighten `clients.conf` to the specific NAS IPs at
that point, and put proper TLS in front of QConnect.

---

## Initial user accounts

Stored in `RADIUS/raddb/mods-config/files/authorize`:

```text
client01    Cleartext-Password := "clientPassword"
server01    Cleartext-Password := "serverPassword"
testuser    Cleartext-Password := "testpw"
```

QConnect-issued keys collected by `qconnect-fetch` are appended to the
sibling file `keys`, using the same line format for familiarity.

