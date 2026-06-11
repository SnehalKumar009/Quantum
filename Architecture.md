# Quantum Secure Client/Server Lab — Architecture Design

## Goal

Build a secure client/server system that combines four independent
security layers:

- **AAA** via RADIUS, with a dedicated **NAS** (Network Access Server)
  mediating between supplicants and the RADIUS server.
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
                                  v
   +----------+  POST /auth  +--------------+   RADIUS UDP   +------------+
   | client01 |------------->| radius-client|--------------->|  radius01  |
   +----------+              |   (the NAS)  |                | FreeRADIUS |
   | server01 |------------->|              |                |            |
   +----+-----+              +--------------+                +------------+
        |                                                          ^
        |                                                 browser  |
        |              +-----------+                      UI tests |
        |              | radius-ui |---------------------------------
        |              +-----------+
        |
        |   --- TLS 1.3 --->   +----------+
        +--------------------> | server01 |   per-conn: QC/QS exchange,
                               +----------+   SHA-256 key derive,
                                              AES-GCM payload.
```

---

## Components

| Component      | Role                                          | Container        | Exposed |
| -------------- | --------------------------------------------- | ---------------- | ------- |
| RADIUS server  | AAA — validates username/password             | `radius01`       | udp 1812/1813 |
| NAS            | HTTP→RADIUS proxy; holds shared RADIUS secret | `radius-client`  | tcp 8082 |
| App client     | Supplicant; one-shot workflow                 | `client01`       | – |
| App server     | Supplicant; long-lived TLS listener           | `server01`       | tcp 8443 |
| Key service    | Issues `(KeyId, Key)` pairs                   | `qconnect`       | tcp 9000 |
| RADIUS UI      | Browser tool to test RADIUS directly          | `radius-ui`      | tcp 8081 |

All six attach to one Docker bridge network: **`quantum-net`**.

---

## Identities & secrets

| Account / secret      | Value             | Owner / consumers                |
| --------------------- | ----------------- | -------------------------------- |
| `client01`            | `clientPassword`  | RADIUS user (supplicant identity)|
| `server01`            | `serverPassword`  | RADIUS user (supplicant identity)|
| `testuser`            | `testpw`          | Smoke-test account               |
| RADIUS shared secret  | `testing123`      | `radius-client` <-> `radius01`   |
| NAS bearer token      | `lab-nas-token`   | supplicants <-> `radius-client`  |

Supplicants **do not** know the RADIUS shared secret. The NAS owns it.

---

## RADIUS attributes on the wire

Standard RFC 2865 attributes always present:

| #  | Name             | Source                                            |
| -- | ---------------- | ------------------------------------------------- |
| 1  | `User-Name`      | supplicant                                        |
| 2  | `User-Password`  | supplicant (encrypted by NAS with shared secret)  |
| 32 | `NAS-Identifier` | NAS (`radius-client-01`)                          |

Vendor-Specific Attributes (Quantum-Lab, vendor ID **`99999`**), defined
in `RADIUS/raddb/dictionary.quantum-lab` and `$INCLUDE`d into the
FreeRADIUS dictionary:

| # | Name             | Type   | Source                                |
| - | ---------------- | ------ | ------------------------------------- |
| 1 | `Quantum-Key-Id` | string | supplicant (from QConnect)            |
| 2 | `Quantum-Key`    | string | supplicant (from QConnect, hex)       |

`radius01` parses and logs the VSAs today, but its **policy currently
authenticates on username/password only**. Policy that consumes the VSAs
will be added next.

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
+------------------------- radius-client (NAS) --------------------------------+
|                                                                              |
|  Build Access-Request:                                                       |
|     User-Name      = username                                                |
|     User-Password  = PwCrypt(password)         (RFC 2865)                    |
|     Quantum-Key-Id = KeyId        (VSA 99999.1)                              |
|     Quantum-Key    = Key          (VSA 99999.2)                              |
|     NAS-Identifier = radius-client-01                                        |
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
|  VSAs are logged but ignored (today).                                        |
+------------------------------------------------------------------------------+
```

---

## Application flow (after auth)

After both supplicants have authenticated, `client01` connects to
`server01` over TLS:

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

Properties:

- **Two-layer crypto.** TLS protects the byte stream; AES-GCM with a key
  derived from independently-contributed QC and QS protects each payload.
- **No single side controls the key.** Each side contributes 256 bits.
- **Tampering detection.** AES-GCM auth tag fails closed (`InvalidTag`).

---

## Network & ports

| Listener        | Container       | Host port (default) |
| --------------- | --------------- | ------------------- |
| RADIUS auth     | `radius01`      | udp 1812            |
| RADIUS acct     | `radius01`      | udp 1813            |
| NAS HTTP        | `radius-client` | tcp 8082            |
| TLS app         | `server01`      | tcp 8443            |
| QConnect HTTP   | `qconnect`      | tcp 9000            |
| RADIUS UI HTTP  | `radius-ui`     | tcp 8081            |

All inter-container traffic flows over the Docker bridge `quantum-net`
using container hostnames (no port mapping needed inside the network).

---

## Startup ordering (top-level compose)

```text
radius01  --+
qconnect  --+--  (no dependencies)
            |
            v
radius-client (depends_on: radius01)        -- healthcheck: GET /healthz
            |
            v
server01   (depends_on: qconnect started, radius-client healthy)
            |                               -- healthcheck: TCP :8443
            v
client01   (depends_on: qconnect started, radius-client healthy,
                         server01 healthy)
```

`radius-ui` only depends on `radius01`.

---

## Design principles

| Principle | How it's realised |
| --------- | ----------------- |
| **Separation of concerns** | RADIUS = identity. TLS = transport. QConnect = key material. Quantum exchange = session key. Each lives in its own container/module. |
| **Supplicants stay small** | They speak only HTTP (to NAS + QConnect) and TLS (to peer). They never carry the RADIUS shared secret. |
| **One auth surface for end users** | The NAS is the single place to add logging, MFA, rate-limit, mTLS, ... without touching `radius01`. |
| **Config from env** | Every host/port/secret comes from environment variables -> same image runs on one host or many. |
| **Cryptographic defence in depth** | Even if TLS were broken, payloads are still AES-GCM with a key only the two peers share. |
| **Future-proof on the wire** | `Quantum-Key-Id` / `Quantum-Key` already ride in every Access-Request; only `radius01` policy needs to change to start enforcing them. |

---

## Phase status

| Phase | Description | Status |
| ----- | ----------- | ------ |
| 1  | Single-host Docker lab on `quantum-net` | DONE |
| 2  | TLS between `client01` <-> `server01` (self-signed, lab mode) | DONE |
| 3  | RADIUS auth | DONE — now via the `radius-client` NAS |
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
Ubuntu Machine A           Ubuntu Machine B           Ubuntu Machine C
+- client01                +- radius-client           +- radius01
                           +- server01                +- qconnect
                                                      +- radius-ui
```

Same Docker images, different `NAS_URL`, `QCONNECT_URL`, `SERVER_HOST`,
`RADIUS_HOST` env vars. Tighten `clients.conf` to the specific NAS IP at
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

