"""
server01 entrypoint.

    1. Authenticate against RADIUS (radius01)             [Phase 3 - LIVE]
    2. Build TLS context from auto-generated cert         [Phase 2 - LIVE]
    3. Accept connections, exchange quantum random        [Phase 4 - LIVE (stub QRNG)]
    4. Derive SessionKey = SHA-256(QC || QS)              [Phase 5 - LIVE]
    5. Decrypt client message, send encrypted ack         [Phase 6 - LIVE]
"""
from __future__ import annotations

import logging
import sys

from .config import load_config
from .radius_auth import RadiusAuthError, authenticate
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
        authenticate(cfg.radius)
    except RadiusAuthError as e:
        log.error("RADIUS auth failed: %s", e)
        return 2

    try:
        serve_forever(cfg.listener)
    except KeyboardInterrupt:
        log.info("Shutdown requested, exiting.")
        return 0


if __name__ == "__main__":
    sys.exit(run())

