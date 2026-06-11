"""
client01 entrypoint.

Workflow (matches Architecture.md):

    1. Register with QConnect            -> (KeyId, Key)
    2. Authenticate via NAS               -> POST /auth {u,p,KeyId,Key}
    3. Generate QC                        -> 32 bytes (Phase 4 stub)
    4. TLS connect to server01
    5. Exchange QS                        -> SessionKey = SHA-256(QC || QS)
    6. Send AES-GCM business message, receive encrypted ack
"""
from __future__ import annotations

import logging
import sys

from .config import load_config
from .crypto_session import EncryptedMessage, decrypt, derive_session_key, encrypt
from .framing import recv_frame, send_frame
from .nas_auth import NasAuthError, authenticate
from .qconnect_client import QConnectError, register
from .quantum import generate_quantum_random
from .tls_client import exchange_quantum, open_tls_connection


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def run() -> int:
    cfg = load_config()
    _setup_logging(cfg.log_level)
    log = logging.getLogger("client01")

    log.info("=== client01 starting ===")

    # --- Step 1: register with QConnect -------------------------------------
    try:
        my_key = register(cfg.qconnect)
    except QConnectError as e:
        log.error("QConnect registration failed: %s", e)
        return 3

    # --- Step 2: authenticate via NAS ---------------------------------------
    try:
        authenticate(cfg.nas, cfg.identity, my_key.key_id, my_key.key)
    except NasAuthError as e:
        log.error("NAS auth failed: %s", e)
        return 2

    # --- Step 3: generate QC ------------------------------------------------
    qc = generate_quantum_random()
    log.info("Generated QC (%d bytes)", len(qc))

    # --- Steps 4-6: TLS + quantum exchange + encrypted message --------------
    with open_tls_connection(cfg.server) as tls:
        qs = exchange_quantum(tls, qc)
        log.info("Received QS (%d bytes)", len(qs))

        session_key = derive_session_key(qc, qs)
        log.info("Derived SessionKey (sha256, %d bytes) - first 8 bytes: %s",
                 len(session_key), session_key[:8].hex())

        plaintext = b"Hello from client01"
        msg = encrypt(session_key, plaintext)
        send_frame(tls, msg.nonce + msg.ciphertext)
        log.info("Sent encrypted business message (%d bytes plaintext)",
                 len(plaintext))

        ack_blob = recv_frame(tls)
        ack = EncryptedMessage(nonce=ack_blob[:12], ciphertext=ack_blob[12:])
        ack_plain = decrypt(session_key, ack)
        log.info("Decrypted server ack: %r", ack_plain)

    log.info("=== client01 finished successfully ===")
    return 0


if __name__ == "__main__":
    sys.exit(run())

