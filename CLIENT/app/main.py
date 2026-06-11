"""
client01 entrypoint.

Executes the full client workflow described in Architecture.md:

    1. Authenticate against RADIUS (radius01)             [Phase 3 - LIVE]
    2. Establish TLS to server01                          [Phase 2 - LIVE]
    3. Generate QC, exchange with server's QS             [Phase 4 - LIVE (stub QRNG)]
    4. Derive SessionKey = SHA-256(QC || QS)              [Phase 5 - LIVE]
    5. Send encrypted business message, receive ack       [Phase 6 - LIVE]
"""
from __future__ import annotations

import logging
import sys

from .config import load_config
from .crypto_session import EncryptedMessage, decrypt, derive_session_key, encrypt
from .framing import recv_frame, send_frame
from .quantum import generate_quantum_random
from .radius_auth import RadiusAuthError, authenticate
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

    # --- Step 1: RADIUS authentication --------------------------------------
    try:
        authenticate(cfg.radius)
    except RadiusAuthError as e:
        log.error("RADIUS auth failed: %s", e)
        return 2

    # --- Step 2/3: TLS connection + quantum exchange ------------------------
    qc = generate_quantum_random()
    log.info("Generated QC (%d bytes)", len(qc))

    with open_tls_connection(cfg.server) as tls:
        qs = exchange_quantum(tls, qc)
        log.info("Received QS (%d bytes)", len(qs))

        # --- Step 4: session key derivation ---------------------------------
        session_key = derive_session_key(qc, qs)
        log.info("Derived SessionKey (sha256, %d bytes) - first 8 bytes: %s",
                 len(session_key), session_key[:8].hex())

        # --- Step 5: encrypted business message over TLS --------------------
        plaintext = b"Hello from client01"
        msg = encrypt(session_key, plaintext)
        send_frame(tls, msg.nonce + msg.ciphertext)
        log.info("Sent encrypted business message (%d bytes plaintext)",
                 len(plaintext))

        # --- Receive encrypted ack ------------------------------------------
        ack_blob = recv_frame(tls)
        ack = EncryptedMessage(nonce=ack_blob[:12], ciphertext=ack_blob[12:])
        ack_plain = decrypt(session_key, ack)
        log.info("Decrypted server ack: %r", ack_plain)

    log.info("=== client01 finished successfully ===")
    return 0


if __name__ == "__main__":
    sys.exit(run())

