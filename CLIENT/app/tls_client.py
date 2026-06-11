"""
TLS client to server01.

Wire protocol inside the TLS tunnel (mirrors server01/app/tls_server.py):

    -> frame 1: QC  (32 bytes)
    <- frame 2: QS  (32 bytes)
       SessionKey = SHA-256(QC || QS)
    -> frame 3: 12-byte nonce || AES-GCM ciphertext (business msg)
    <- frame 4: 12-byte nonce || AES-GCM ciphertext (ack)

Cert verification:
  - In Phase 2 of the lab we use a self-signed server cert and skip
    verification (TLS_VERIFY=false). A clear WARNING is logged.
  - To switch to verified TLS, mount the lab CA into the client image and
    set TLS_VERIFY=true plus TLS_CA_FILE.
"""
from __future__ import annotations

import logging
import os
import socket
import ssl
from contextlib import contextmanager

from .config import ServerConfig
from .framing import recv_frame, send_frame
from .quantum import QRNG_BYTES

logger = logging.getLogger(__name__)


def _build_ssl_context() -> ssl.SSLContext:
    verify = os.environ.get("TLS_VERIFY", "false").lower() == "true"
    ca_file = os.environ.get("TLS_CA_FILE")

    ctx = ssl.create_default_context(
        ssl.Purpose.SERVER_AUTH,
        cafile=ca_file if verify else None,
    )
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    if not verify:
        logger.warning(
            "TLS cert verification DISABLED (lab mode). "
            "Set TLS_VERIFY=true and TLS_CA_FILE=<path> for production."
        )
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


@contextmanager
def open_tls_connection(cfg: ServerConfig):
    ctx = _build_ssl_context()
    raw = socket.create_connection((cfg.host, cfg.port), timeout=10)
    try:
        tls = ctx.wrap_socket(raw, server_hostname=cfg.host)
        logger.info(
            "TLS connection established to %s:%d (cipher=%s)",
            cfg.host, cfg.port, tls.cipher(),
        )
        try:
            yield tls
        finally:
            try:
                tls.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            tls.close()
    except Exception:
        raw.close()
        raise


def exchange_quantum(tls_sock: ssl.SSLSocket, qc: bytes) -> bytes:
    """Send QC over the TLS socket, receive and return QS."""
    send_frame(tls_sock, qc)
    qs = recv_frame(tls_sock)
    if len(qs) != QRNG_BYTES:
        raise ValueError(f"unexpected QS length: {len(qs)}")
    return qs

