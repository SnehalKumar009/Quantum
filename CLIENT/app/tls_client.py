"""
TLS client to server01.

Wire protocol inside the TLS tunnel (mirrors server01/app/tls_server.py):

    -> frame 1 (QC):  "<client_sae_id>|<key_id_c>"   (ASCII)
       Client first called ETSI 014 enc_keys against the KME with the
       server SAE as the slave, getting (key_id_c, key_c). Server uses
       (client_sae_id, key_id_c) to dec_keys the same key.
    <- frame 2 (QS):  "<server_sae_id>|<key_id_s>"   (ASCII)
       Server in turn enc_keys for the client SAE. Client uses
       (server_sae_id, key_id_s) to dec_keys that key.

       Both sides then derive:
            SessionKey = SHA-256(key_c || key_s)

    -> frame 3: 12-byte nonce || AES-GCM ciphertext (business msg)
    <- frame 4: 12-byte nonce || AES-GCM ciphertext (ack)

Cert verification:
  - In Phase 2 of the lab we use a self-signed server cert and skip
    verification (TLS_VERIFY=false). A clear WARNING is logged.
  - To switch to verified TLS, mount the lab CA into the client image and
    set TLS_VERIFY=true plus TLS_CA_FILE.
"""
from __future__ import annotations

import base64
import logging
import os
import socket
import ssl
from contextlib import contextmanager
from typing import Tuple

from .config import QkdConfig, ServerConfig
from .framing import recv_frame, send_frame
from .qkd_client import QkdError, dec_key, enc_key, own_sae_id

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


def _parse_qkd_frame(frame: bytes, label: str) -> Tuple[str, str]:
    """Parse a '<master_sae_id>|<key_id>' ASCII frame."""
    try:
        text = frame.decode("ascii")
    except UnicodeDecodeError as e:
        raise ValueError(f"{label} frame is not ASCII: {frame!r}") from e
    if "|" not in text:
        raise ValueError(
            f"unexpected {label} frame format (want 'master_sae|key_id'): {text!r}"
        )
    master_sae_id, key_id = text.split("|", 1)
    master_sae_id, key_id = master_sae_id.strip(), key_id.strip()
    if not master_sae_id or not key_id:
        raise ValueError(f"empty master_sae_id or key_id in {label}: {text!r}")
    return master_sae_id, key_id


def exchange_quantum(tls_sock: ssl.SSLSocket,
                     qkd_cfg: QkdConfig) -> Tuple[bytes, bytes]:
    """
    Run the per-connection QKD exchange and return (qc_key_bytes, qs_key_bytes).

    Steps:
      1. enc_keys against the KME with the data-plane server SAE as slave
         -> (key_id_c, key_c). Send "<own_sae>|<key_id_c>" as the QC frame.
      2. Receive the server's QS frame "<server_sae>|<key_id_s>",
         dec_keys against the KME to retrieve key_s.
      3. Return both raw key byte strings to the caller.
    """
    if not qkd_cfg.data_peer_sae_id:
        raise ValueError(
            "QKD_DATA_PEER_SAE_ID is empty - cannot run data-plane enc_keys "
            "for the server SAE"
        )

    # ---- 1) enc_keys: we are master, server SAE is slave -----------------
    own_id = own_sae_id(qkd_cfg)
    logger.info(
        "enc_keys: master=%s (self) slave=%s (server)",
        own_id, qkd_cfg.data_peer_sae_id,
    )
    try:
        qk_c = enc_key(qkd_cfg, qkd_cfg.data_peer_sae_id)
    except QkdError as e:
        raise ValueError(f"enc_keys failed: {e}") from e
    qc_key_bytes = base64.b64decode(qk_c.key)
    logger.info(
        "QC QKD key obtained: key_id=%s len=%d (first 8B=%s)",
        qk_c.key_id, len(qc_key_bytes), qc_key_bytes[:8].hex(),
    )

    # ---- Send QC frame ---------------------------------------------------
    qc_payload = f"{own_id}|{qk_c.key_id}".encode("ascii")
    send_frame(tls_sock, qc_payload)
    logger.info("Sent QC frame (%d bytes ASCII): %s",
                len(qc_payload), qc_payload.decode("ascii"))

    # ---- 2) Receive QS frame, dec_keys the server-issued key -------------
    qs_frame = recv_frame(tls_sock)
    server_sae_id, key_id_s = _parse_qkd_frame(qs_frame, "QS")
    logger.info(
        "QS frame parsed: master_sae_id=%s key_id=%s -> calling dec_keys",
        server_sae_id, key_id_s,
    )
    try:
        qk_s = dec_key(qkd_cfg, server_sae_id, key_id_s)
    except QkdError as e:
        raise ValueError(f"dec_keys failed for key_id={key_id_s}: {e}") from e
    qs_key_bytes = base64.b64decode(qk_s.key)
    logger.info(
        "QS QKD key retrieved from KME: key_id=%s len=%d (first 8B=%s)",
        qk_s.key_id, len(qs_key_bytes), qs_key_bytes[:8].hex(),
    )

    return qc_key_bytes, qs_key_bytes
