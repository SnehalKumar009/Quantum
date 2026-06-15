"""
server01 entrypoint.

    1. Fetch a QKD key from qConnect (ETSI 014, enc_keys)  -> (key_id, key)
    2. Authenticate via NAS — sending {username, password, key_id, master_sae_id}.
       The key itself never leaves this process; RADIUS will independently
       fetch it from qConnect by key_id.
    3. Listen on TLS (8443) and serve the application protocol.
"""
from __future__ import annotations

import logging
import sys

from .config import load_config
from .nas_auth import NasAuthError, authenticate
from .qkd_client import QkdError, enc_key, own_sae_id
from .tls_server import serve_forever


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def run() -> int:
    cfg = load_config()
    _setup_logging(cfg.log_level)
    log = logging.getLogger("server01")

    log.info("=== server01 starting ===")

    # ---- 1) get a quantum key from qConnect ------------------------------
    try:
        master_sae_id = own_sae_id(cfg.qkd)
        log.info("server01 own SAE_ID (master) = %s", master_sae_id)
        log.info("Requesting enc_keys from KME=%s for peer (slave) SAE=%s",
                 cfg.qkd.kme_url, cfg.qkd.peer_sae_id)
        my_key = enc_key(cfg.qkd, cfg.qkd.peer_sae_id)
        log.info("Got QKD key from qConnect: key_id=%s (key withheld)", my_key.key_id)
    except QkdError as e:
        log.error("qConnect KME enc_keys failed: %s", e)
        return 3

    # ---- 2) authenticate via the NAS using key_id + master_sae_id ---------
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

    # ---- 3) serve forever -------------------------------------------------
    try:
        serve_forever(cfg.listener, cfg.qkd)
    except KeyboardInterrupt:
        log.info("Shutdown requested, exiting.")
        return 0


if __name__ == "__main__":
    sys.exit(run())

