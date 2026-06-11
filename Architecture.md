# Quantum Secure Client/Server Lab — Architecture Design

## Goal

Build a secure client/server system that:

- Uses **RADIUS** for Authentication, Authorization, and Accounting (AAA)
- Uses **TLS** for transport security
- Uses a **Quantum Random Number Generator (QRNG)** to establish an application-level session key
- Runs initially in **Docker containers** on a single Ubuntu machine
- Can later be **distributed across multiple Ubuntu machines**

---

## High-Level Architecture

```text
                +------------------+
                |   RADIUS Server  |
                |       AAA        |
                +------------------+
                  ^              ^
                  |              |
       username/password   username/password
                  |              |
             +---------+    +---------+
             | Client  |    | Server  |
             +---------+    +---------+

         Client <------ TLS ------> Server
                         |
                         v
              Quantum Random Exchange
                         |
                         v
               Application Session Key
```

---

## Responsibilities

### RADIUS Server

Responsible for:

- Authentication
- Authorization
- Accounting

Examples:

- Validate username/password
- Determine client roles
- Log authentication events

RADIUS does **NOT**:

- Encrypt application traffic
- Participate in TLS
- Generate quantum session keys

### Client

Responsibilities:

- Authenticate against RADIUS
- Verify successful authentication
- Establish TLS connection to server
- Generate quantum random value
- Exchange quantum value with server
- Derive application session key
- Send encrypted business messages

Identity:

- **Username:** `client01`
- **Password:** `********`

### Server

Responsibilities:

- Authenticate against RADIUS
- Verify successful authentication
- Accept TLS connections
- Generate quantum random value
- Exchange quantum value with client
- Derive application session key
- Process encrypted business messages

Identity:

- **Username:** `server01`
- **Password:** `********`

---

## Authentication Flow

### Client Authentication

```text
client01
    |
    | username/password
    v
radius01
    |
    v
Access-Accept
```

### Server Authentication

```text
server01
    |
    | username/password
    v
radius01
    |
    v
Access-Accept
```

---

## Communication Flow

### Step 1 — Authenticate

```text
Client -> RADIUS
Server -> RADIUS
```

Both receive:

- `Access-Accept`

### Step 2 — TLS Establishment

```text
Client <---- TLS ----> Server
```

TLS provides:

- Confidentiality
- Integrity
- Transport security

### Step 3 — Quantum Exchange

After TLS is established:

```text
Client -> QuantumRandomClient
Server -> QuantumRandomServer
```

Example:

- `QC` = Client Quantum Random Value
- `QS` = Server Quantum Random Value

### Step 4 — Session Key Derivation

```text
SessionKey = Hash(QC || QS)
```

Both sides independently derive the same session key.

### Step 5 — Secure Business Communication

```text
Encrypt(Data, SessionKey)
```

Business messages are protected using the application-level session key.

---

## Deployment Phases

### Phase 1 — Single Host

Single Ubuntu machine with Docker containers:

```text
Ubuntu Host
├── radius01
├── client01
└── server01
```

All containers share a Docker network.

### Phase 2 — TLS

Add TLS between client and server:

```text
client01 <---- TLS ----> server01
```

### Phase 3 — RADIUS Authentication

```text
client01 -> radius01
server01 -> radius01
```

### Phase 4 — Quantum Random Number Generator

Generate:

- `QC`
- `QS`

### Phase 5 — Session Key

Derive application session key:

```text
SessionKey = Hash(QC || QS)
```

### Phase 6 — Encrypted Payloads

Encrypt business payloads:

```text
Application Data
      ↓
Encrypt(SessionKey)
      ↓
  TLS Transport
```

---

## Future Multi-Machine Deployment

```text
Ubuntu Machine A
└── client01

Ubuntu Machine B
└── server01

Ubuntu Machine C
└── radius01
```

Communication:

```text
client01 ---> radius01
server01 ---> radius01

client01 <---- TLS ----> server01
```

RADIUS will be reachable using a public IP or routed network address.

---

## Design Principles

### AAA Handles Identity

Questions answered:

- Who are you?
- Are you authorized?
- What should be logged?

Handled by:

- RADIUS

### TLS Handles Transport Security

Provides:

- Encryption
- Integrity
- Secure transport

Handled by:

- TLS / OpenSSL

### Quantum Layer Handles Session Security

Provides:

- Additional entropy
- Session key generation
- Key rotation capability

Handled by:

- Application layer

---

## Initial User Accounts

| Username   | Password         |
| ---------- | ---------------- |
| `client01` | `clientPassword` |
| `server01` | `serverPassword` |

These accounts are stored in the RADIUS server.

