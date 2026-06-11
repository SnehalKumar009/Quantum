"""
server01 entrypoint.

    1. Register with QConnect            -> (KeyId, Key)
    2. Authenticate via NAS               -> POST /auth {u,p,KeyId,Key}
    3. Listen on TLS (8443) and serve quantum/AES-GCM protocol
"""
from __future__ import annotations

import logging
import sys

from .config import load_config
from .nas_auth import NasAuthError, authenticate
from .qconnect_client import QConnectError, register
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

    try:
        my_key = register(cfg.qconnect)
    except QConnectError as e:
        log.error("QConnect registration failed: %s", e)
        return 3

    try:
        authenticate(cfg.nas, cfg.identity, my_key.key_id, my_key.key)
    except NasAuthError as e:
        log.error("NAS auth failed: %s", e)
        return 2

    try:
        serve_forever(cfg.listener)
    except KeyboardInterrupt:
        log.info("Shutdown requested, exiting.")
        return 0


if __name__ == "__main__":
    sys.exit(run())

