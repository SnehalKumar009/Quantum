"""
client01 entrypoint.

Workflow:

    1. Fetch a QKD key from qConnect (ETSI 014, enc_keys) -> (key_id, key)
    2. Authenticate via NAS — send {username, password, key_id, master_sae_id}.
       The key itself never leaves this process; RADIUS independently fetches
       it from qConnect by key_id (dec_keys).
    3. Generate QC                        -> 32 bytes (Phase 4 stub)
    4. TLS connect to server01
    5. Exchange QS                        -> SessionKey = SHA-256(QC || QS)
    6. Send AES-GCM business message, receive encrypted ack
"""
from __future__ import annotations

import logging
import os
import sys
import time

from .config import load_config
from .crypto_session import EncryptedMessage, decrypt, derive_session_key, encrypt
from .framing import recv_frame, send_frame
from .nas_auth import NasAuthError, authenticate
from .qkd_client import QkdError, enc_key, own_sae_id
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

    # --- Step 1: get a quantum key from qConnect ---------------------------
    try:
        master_sae_id = own_sae_id(cfg.qkd)
        log.info("client01 own SAE_ID (master) = %s", master_sae_id)
        log.info("Requesting enc_keys from KME=%s for peer (slave) SAE=%s",
                 cfg.qkd.kme_url, cfg.qkd.peer_sae_id)
        my_key = enc_key(cfg.qkd, cfg.qkd.peer_sae_id)
        log.info("Got QKD key from qConnect: key_id=%s (key withheld)",
                 my_key.key_id)
    except QkdError as e:
        log.error("qConnect KME enc_keys failed: %s", e)
        return 3

    # --- Optional pause for manual failure-mode testing --------------------
    # Lets an operator tamper with / consume the key in qConnect
    # between enc_keys and the NAS auth call below, so the resulting
    # Access-Reject can be observed end-to-end. Default 0 = no delay.
    pre_auth_delay = float(os.environ.get("PRE_AUTH_DELAY_SECONDS", "0"))
    if pre_auth_delay > 0:
        log.info(
            "PRE_AUTH_DELAY_SECONDS=%.1f - sleeping before NAS auth "
            "(window to consume key_id=%s on qConnect).",
            pre_auth_delay, my_key.key_id,
        )
        time.sleep(pre_auth_delay)

    # --- Step 2: authenticate via NAS using key_id + master_sae_id ---------
    try:
        authenticate(
            cfg.nas,
            cfg.identity,
            key_id=my_key.key_id,
            master_sae_id=master_sae_id,
        )
    except NasAuthError as e:
        log.error("NAS auth failed: %s", e)
        return 2

    # --- Step 3: generate QC ----------------------------------------------
    qc = generate_quantum_random()
    log.info("Generated QC (%d bytes)", len(qc))

    # --- Steps 4-6: TLS + quantum exchange + encrypted message ------------
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

