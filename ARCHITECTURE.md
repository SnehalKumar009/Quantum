# Quantum Secure Lab — Architecture Diagram

Single-page, arrow-by-arrow view of every wire in the lab: what protocol
it speaks and what it carries. For configuration, env vars, and run
instructions see [`README.md`](./README.md).

---

## Legend

```
──►  request / send             ◄──   reply / receive
══►  encrypted channel          •••►  policy/internal call (no socket)

Edge label format:
    [protocol]  payload summary
```

Protocols in use:

| Tag | Meaning |
| --- | --- |
| `TCP` | plain TCP socket |
| `UDP/1812` | RADIUS (RFC 2865) over UDP |
| `HTTP` | plain HTTP (cleartext, internal Docker network only) |
| `HTTPS+mTLS` | TLS 1.2/1.3 with **both** client + server certificates (ETSI 014 to KME) |
| `TLS` | TLS 1.2 with server cert only (lab self-signed); client cert disabled |
| `app-AES-GCM` | AES-256-GCM inside the TLS tunnel, key = QKD-derived SessionKey |
| `exec` | FreeRADIUS `rlm_exec` fork into a helper script (in-process) |

---

## 1. Big picture — every component, every edge

```
                            ┌──────────────────────────────────┐
                            │  qConnect KME (real, off-host)   │
                            │  https://192.168.10.233:50555    │
                            │  ETSI GS QKD 014 (REST + mTLS)   │
                            └─────────────▲────────────────────┘
                                          │
       ┌──────────────────────┬───────────┼────────────┬──────────────────────┐
       │                      │           │            │                      │
       │ HTTPS+mTLS           │ HTTPS+mTLS│            │ HTTPS+mTLS           │
       │ enc_keys / dec_keys  │           │            │ enc_keys / dec_keys  │
       │ (sae-client01 bundle)│           │            │ (sae-server01 bundle)│
       │                      │           │            │                      │
       │                      │ HTTPS+mTLS│            │                      │
       │                      │ dec_keys  │            │                      │
       │                      │ (sae-     │            │                      │
       │                      │  radius01 │            │                      │
       │                      │  bundle)  │            │                      │
       ▼                      │           │            │                      ▼
 ┌─────────────┐              │           │            │              ┌─────────────┐
 │  client01   │              │           │            │              │  server01   │
 │  (Python)   │              │           │            │              │  (Python)   │
 │ SAE: client │              │           │            │              │ SAE: server │
 └──┬───────▲──┘              │           │            │              └──▲───────┬──┘
    │       │                 │           │            │                 │       │
    │   ╔═══════════════════════════════════════════════════════════════════╗    │
    │   ║   TLS  (8443/tcp, self-signed, server-auth only)                  ║    │
    │   ║                                                                   ║    │
    │   ║   frame 1  QC = "<sae-client01>|<key_id_c>"           (ASCII)     ║    │
    │   ║   frame 2  QS = "<sae-server01>|<key_id_s>"           (ASCII)     ║    │
    │   ║                                                                   ║    │
    │   ║   SessionKey = SHA-256(key_c || key_s)   [derived locally]        ║    │
    │   ║                                                                   ║    │
    │   ║   frame 3  app-AES-GCM(nonce || ciphertext)  "Hello from client"  ║    │
    │   ║   frame 4  app-AES-GCM(nonce || ciphertext)  "ack: Hello…"        ║    │
    │   ╚═══════════════════════════════════════════════════════════════════╝    │
    │                                                                            │
    │ HTTP /auth                                                       HTTP /auth│
    │ Bearer lab-nas-token                                Bearer lab-nas-token   │
    │ {username,password,KeyId,MasterSaeId}      {username,password,KeyId,MSA}   │
    ▼                                                                            ▼
 ┌──────────────────────┐                                      ┌──────────────────────┐
 │ client-radiusclient  │                                      │ server-radiusclient  │
 │  NAS (FastAPI+pyrad) │                                      │  NAS (FastAPI+pyrad) │
 │  NAS-Id:             │                                      │  NAS-Id:             │
 │  client-radiusclient │                                      │  server-radiusclient │
 │  -01                 │                                      │  -01                 │
 └────────┬─────────────┘                                      └─────────────┬────────┘
          │                                                                  │
          │ UDP/1812  Access-Request                                         │
          │   User-Name, User-Password (PwCrypt),                            │
          │   NAS-Identifier, Quantum-Key-Id (VSA 99999:1),                  │
          │   Quantum-Master-SAE-ID (VSA 99999:3)                            │
          │                                                                  │
          │       UDP/1812  Access-Accept / Access-Reject + Reply-Message    │
          │                                                                  │
          └─────────────────────┐                ┌──────────────────────────-┘
                                ▼                ▼
                          ┌──────────────────────────┐
                          │        radius01          │
                          │   FreeRADIUS 3.2.5       │
                          │                          │
                          │  authorize {             │
                          │    quantum_key_check  •••┼─────┐
                          │    ...                   │     │  exec  (rlm_exec)
                          │    pap                   │     │
                          │  }                       │     ▼
                          │                          │  /usr/local/bin/
                          │                          │     quantum-key-check
                          │                          │       │
                          │                          │       │ fork
                          │                          │       ▼
                          │                          │     qkd-dec-key.sh
                          │                          │       │
                          │                          │       └──► HTTPS+mTLS
                          │                          │            dec_keys @ KME
                          │                          │            (sae-radius01 bundle)
                          │                          │       ◄── 200 + {keys[].key}
                          │                          │     -> stdout "OK" | "FAIL:…"
                          └──────────▲───────────────┘
                                     │
                                     │ UDP/1812 Access-Request (no VSAs)
                                     │ UDP/1812 Access-Accept / Access-Reject
                                     │
                          ┌──────────┴───────────────┐
                          │        radius-ui         │
                          │  FastAPI :8081           │
                          │  HTML form, no VSAs      │
                          │  (NAS-Identifier=        │
                          │     "radius-ui")         │
                          └──────────────────────────┘
                                     ▲
                                     │ HTTP  (browser, port 8081)
                                     │
                                  Operator
```

All Docker containers share the bridge network **`quantum-net`**.

---

## 2. Auth plane — what crosses each wire, in order

For one supplicant boot (`client01` shown; `server01` is identical with
its own SAE):

```
1.  client01  ──HTTPS+mTLS──►  KME
        GET /api/v1/keys/{sae-radius01-UUID}/enc_keys
        client cert = sae-client01.crt.pem
2.  client01  ◄──HTTPS+mTLS──  KME
        200  { "keys": [{ "key_ID": "<uuid>", "key": "<base64>" }] }

3.  client01  ──HTTP──►  client-radiusclient   (POST /auth, Bearer token)
        {
          "username":    "client01",
          "password":    "clientPassword",
          "KeyId":       "<uuid from step 2>",
          "MasterSaeId": "<sae-client01-UUID>"
        }

4.  client-radiusclient  ──UDP/1812──►  radius01
        Access-Request
          User-Name              = client01
          User-Password          = PwCrypt(clientPassword, RADIUS_SECRET)
          NAS-Identifier         = client-radiusclient-01
          Quantum-Key-Id         = <uuid>           (vendor 99999, attr 1)
          Quantum-Master-SAE-ID  = <sae-client01>   (vendor 99999, attr 3)

5.  radius01  •••►  /usr/local/bin/quantum-key-check  <KeyId> <MasterSaeId>
        (rlm_exec fork; env re-loaded from /etc/qkd-env)
6.       └──►  /usr/local/bin/qkd-dec-key  <MasterSaeId> <KeyId>
7.            └──HTTPS+mTLS──►  KME
                  GET /api/v1/keys/{MasterSaeId}/dec_keys?key_ID={KeyId}
                  client cert = sae-radius01.crt.pem
8.                ◄──HTTPS+mTLS──  KME
                  200  { "keys": [{ "key_ID":..., "key":... }] }
                  -> exit 0 -> stdout "OK"

9.  radius01  ──UDP/1812──►  client-radiusclient
        Access-Accept   Reply-Message := "Welcome client01"
        (or Access-Reject + reason on any failure)

10. client-radiusclient  ──HTTP──►  client01
        200 { ok:true, reply_message:"Welcome client01" }
        (or 401 with reason on Access-Reject)
```

Key property: the **key bytes never cross any non-mTLS link**. Only the
`key_ID` UUID and the master `SAE_ID` are transported in the RADIUS
packet.

---

## 3. Data plane — per TLS connection between client01 and server01

```
TCP   client01:* ──SYN/SYN-ACK/ACK──► server01:8443

TLS   ClientHello, ServerHello, server Certificate, ServerKeyExchange,
      ClientKeyExchange, ChangeCipherSpec, Finished, ...
      (self-signed cert on server side; client side has TLS_VERIFY=false
       so no client cert is sent and the server cert is accepted blind)

------ everything below rides inside the TLS record stream ------

A.  client01  ──HTTPS+mTLS──►  KME
        GET /api/v1/keys/{sae-server01-UUID}/enc_keys
B.  client01  ◄──HTTPS+mTLS──  KME
        200 { keys:[{key_ID: kid_c, key: key_c_b64}] }

C.  client01  ──TLS frame 1──►  server01
        QC = "<sae-client01-UUID>|<kid_c>"   (ASCII)

D.  server01  ──HTTPS+mTLS──►  KME
        GET /api/v1/keys/{sae-client01-UUID}/dec_keys?key_ID={kid_c}
E.  server01  ◄──HTTPS+mTLS──  KME
        200 { keys:[{key_ID: kid_c, key: key_c_b64}] }
        (server now holds key_c)

F.  server01  ──HTTPS+mTLS──►  KME
        GET /api/v1/keys/{sae-client01-UUID}/enc_keys
G.  server01  ◄──HTTPS+mTLS──  KME
        200 { keys:[{key_ID: kid_s, key: key_s_b64}] }

H.  server01  ──TLS frame 2──►  client01
        QS = "<sae-server01-UUID>|<kid_s>"   (ASCII)

I.  client01  ──HTTPS+mTLS──►  KME
        GET /api/v1/keys/{sae-server01-UUID}/dec_keys?key_ID={kid_s}
J.  client01  ◄──HTTPS+mTLS──  KME
        200 { keys:[{key_ID: kid_s, key: key_s_b64}] }
        (client now holds key_s)

K.  both sides locally:
        SessionKey = SHA-256( base64.decode(key_c_b64)
                           || base64.decode(key_s_b64) )       # 32 bytes

L.  client01  ──TLS frame 3──►  server01
        12-byte nonce || AES-GCM(SessionKey, "Hello from client01")
M.  server01  ──TLS frame 4──►  client01
        12-byte nonce || AES-GCM(SessionKey, "ack: Hello from client01")

TLS   close_notify, FIN/FIN-ACK
```

Per connection that is:
- **4 KME round-trips over HTTPS+mTLS** (two `enc_keys`, two `dec_keys`).
- **4 length-prefixed frames over TLS** (`QC`, `QS`, business msg, ack).
- **2 distinct QKD keys consumed** (`kid_c`, `kid_s`).

The two `Derived SessionKey first 8 bytes: <X>` log lines (one on each
side) **must show the same `<X>`** — that's the live integrity check.

---

## 4. Edge-by-edge summary table

| # | From → To | Protocol | Carries |
|---|-----------|----------|---------|
| 1 | client01 / server01 → KME | `HTTPS+mTLS` (ETSI 014) | `GET /api/v1/keys/<slave>/enc_keys` |
| 2 | KME → client01 / server01 | `HTTPS+mTLS` | `{ key_ID, key (b64) }` |
| 3 | client01 → client-radiusclient | `HTTP` | `POST /auth  {username,password,KeyId,MasterSaeId}`  +  `Authorization: Bearer …` |
| 3' | server01 → server-radiusclient | `HTTP` | same shape |
| 4 | *-radiusclient → radius01 | `UDP/1812` (RADIUS) | Access-Request + VSAs `Quantum-Key-Id`, `Quantum-Master-SAE-ID` |
| 5 | radius01 → quantum-key-check.sh | `exec` (rlm_exec) | argv: `KeyId MasterSaeId`, stdout: `OK` / `FAIL:…` |
| 6 | radius01 (qkd-dec-key.sh) → KME | `HTTPS+mTLS` | `GET /api/v1/keys/<MasterSaeId>/dec_keys?key_ID=<KeyId>` |
| 7 | radius01 → *-radiusclient | `UDP/1812` | Access-Accept / Access-Reject + Reply-Message |
| 8 | *-radiusclient → supplicant | `HTTP` | 200 / 401 + JSON `{ok, reply_message, reason}` |
| 9 | client01 ↔ server01 | `TCP` | TLS handshake (server-auth, self-signed) |
| 10 | client01 → server01 | `TLS frame 1` | QC = `"<client_sae>|<kid_c>"` (ASCII) |
| 11 | server01 → client01 | `TLS frame 2` | QS = `"<server_sae>|<kid_s>"` (ASCII) |
| 12 | client01 ↔ server01 | `TLS` + `app-AES-GCM` | frames 3/4: `nonce(12B) || AES-GCM(SessionKey, plaintext)` |
| 13 | operator → radius-ui | `HTTP` (browser :8081) | HTML form `(username, password)` |
| 14 | radius-ui → radius01 | `UDP/1812` | Access-Request (no VSAs, NAS-Identifier=`radius-ui`) |

---

## 5. Where each cryptographic key lives

```
KME-issued key (per enc_keys/dec_keys pair):
   ┌────────────────────────────────────────────────────────────┐
   │ Lives only at: the master SAE (from enc_keys) and the      │
   │ slave SAE (after dec_keys). Identified by key_ID UUID.     │
   │ Transferred on the wire ONLY inside HTTPS+mTLS responses.  │
   └────────────────────────────────────────────────────────────┘

TLS record-layer keys (per TLS connection):
   ┌────────────────────────────────────────────────────────────┐
   │ Derived locally by OpenSSL on both client01 and server01   │
   │ from the ECDHE shared secret + client_random + server_     │
   │ random. Never appear in any application log.               │
   └────────────────────────────────────────────────────────────┘

App SessionKey (per TLS connection):
   ┌────────────────────────────────────────────────────────────┐
   │ SessionKey = SHA-256(key_c || key_s)                       │
   │ Derived locally on both ends from the two KME-issued       │
   │ keys. Used by AES-256-GCM for the business messages        │
   │ INSIDE the TLS tunnel (defence in depth).                  │
   └────────────────────────────────────────────────────────────┘

RADIUS shared secret:
   ┌────────────────────────────────────────────────────────────┐
   │ testing123  (in clients.conf + each NAS env). Used to      │
   │ PwCrypt the User-Password attribute and authenticate the   │
   │ NAS to the RADIUS server.                                  │
   └────────────────────────────────────────────────────────────┘

NAS bearer token:
   ┌────────────────────────────────────────────────────────────┐
   │ lab-nas-token  (in supplicant + NAS env). Guards the HTTP  │
   │ /auth endpoint on each NAS.                                │
   └────────────────────────────────────────────────────────────┘
```

