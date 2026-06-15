"""
TLS listener that implements the Phase 2 + Phase 4-6 protocol.

Per connection (inside the TLS tunnel):

    <- frame 1 (QC):  "<client_sae_id>|<key_id_c>"   (ASCII)
       Server dec_keys this against the KME to retrieve key_c.
    -> frame 2 (QS):  "<server_sae_id>|<key_id_s>"   (ASCII)
       Server first enc_keys with the client SAE as the slave -> key_s.
       Client dec_keys (server_sae_id, key_id_s) -> key_s.

       Both sides then derive:
            SessionKey = SHA-256(key_c || key_s)

    <- frame 3: 12-byte nonce || ciphertext from client (AES-GCM)
    -> frame 4: 12-byte nonce || ciphertext from server (AES-GCM ack)
"""
from __future__ import annotations

import base64
import logging
import socket
import ssl
import threading
from typing import Tuple

from .config import QkdConfig, TlsListenerConfig
from .crypto_session import EncryptedMessage, decrypt, derive_session_key, encrypt
from .framing import recv_frame, send_frame
from .qkd_client import QkdError, dec_key, enc_key, own_sae_id

logger = logging.getLogger(__name__)


def _build_ssl_context(cfg: TlsListenerConfig) -> ssl.SSLContext:
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=cfg.cert_file, keyfile=cfg.key_file)
    return ctx


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


def _handle_connection(tls_sock: ssl.SSLSocket, peer: tuple, qkd_cfg: QkdConfig) -> None:
    log = logging.getLogger(f"server01.conn.{peer[0]}:{peer[1]}")
    try:
        if not qkd_cfg.data_peer_sae_id:
            raise QkdError(
                "QKD_DATA_PEER_SAE_ID is empty - cannot run data-plane "
                "enc_keys for the client SAE"
            )

        # ---- Phase 4a: receive client's QC frame, dec_keys it -------------
        qc_frame = recv_frame(tls_sock)
        client_sae_id, key_id_c = _parse_qkd_frame(qc_frame, "QC")
        log.info(
            "QC frame parsed: master_sae_id=%s key_id=%s -> calling dec_keys",
            client_sae_id, key_id_c,
        )
        qk_c = dec_key(qkd_cfg, client_sae_id, key_id_c)
        qc_key_bytes = base64.b64decode(qk_c.key)
        log.info(
            "QC QKD key retrieved: key_id=%s len=%d (first 8B=%s)",
            qk_c.key_id, len(qc_key_bytes), qc_key_bytes[:8].hex(),
        )

        # ---- Phase 4b: enc_keys for the client SAE -> QS frame -----------
        master_sae_id = own_sae_id(qkd_cfg)
        log.info(
            "enc_keys: master=%s (self) slave=%s (client)",
            master_sae_id, qkd_cfg.data_peer_sae_id,
        )
        qk_s = enc_key(qkd_cfg, qkd_cfg.data_peer_sae_id)
        qs_key_bytes = base64.b64decode(qk_s.key)
        log.info(
            "QS QKD key obtained: key_id=%s len=%d (first 8B=%s)",
            qk_s.key_id, len(qs_key_bytes), qs_key_bytes[:8].hex(),
        )

        qs_payload = f"{master_sae_id}|{qk_s.key_id}".encode("ascii")
        send_frame(tls_sock, qs_payload)
        log.info("Sent QS frame (%d bytes ASCII): %s",
                 len(qs_payload), qs_payload.decode("ascii"))

        # ---- Phase 5: session key -----------------------------------------
        session_key = derive_session_key(qc_key_bytes, qs_key_bytes)
        log.info("Derived SessionKey first 8 bytes: %s", session_key[:8].hex())

        # ---- Phase 6: receive encrypted business message -------------------
        blob = recv_frame(tls_sock)
        if len(blob) < 12:
            raise ValueError("ciphertext frame too short")
        msg = EncryptedMessage(nonce=blob[:12], ciphertext=blob[12:])
        plaintext = decrypt(session_key, msg)
        log.info("Decrypted message from client: %r", plaintext)

        # ---- Encrypted ack ------------------------------------------------
        reply = b"ack: " + plaintext
        ack = encrypt(session_key, reply)
        send_frame(tls_sock, ack.nonce + ack.ciphertext)
        log.info("Sent encrypted ack (%d bytes ciphertext)", len(ack.ciphertext))
    except Exception:
        log.exception("connection handler error")
    finally:
        try:
            tls_sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        tls_sock.close()


def serve_forever(cfg: TlsListenerConfig, qkd_cfg: QkdConfig) -> None:
    ctx = _build_ssl_context(cfg)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as raw:
        raw.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        raw.bind((cfg.host, cfg.port))
        raw.listen(16)
        logger.info("TLS listener ready on %s:%d (cert=%s)",
                    cfg.host, cfg.port, cfg.cert_file)

        while True:
            client_sock, peer = raw.accept()
            try:
                tls_sock = ctx.wrap_socket(client_sock, server_side=True)
            except ssl.SSLError as e:
                logger.warning("TLS handshake failed with %s: %s", peer, e)
                client_sock.close()
                continue
            logger.info("Accepted TLS connection from %s", peer)
            t = threading.Thread(
                target=_handle_connection,
                args=(tls_sock, peer, qkd_cfg),
                name=f"conn-{peer[0]}:{peer[1]}",
                daemon=True,
            )
            t.start()
