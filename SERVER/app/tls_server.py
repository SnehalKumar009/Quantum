"""
TLS listener that implements the Phase 2 + Phase 4-6 protocol.

Per connection (inside the TLS tunnel):

    <- frame 1: QC  (32 bytes)              from client
    -> frame 2: QS  (32 bytes)              from server (this side)
       SessionKey = SHA-256(QC || QS)
    <- frame 3: 12-byte nonce || ciphertext from client (AES-GCM)
    -> frame 4: 12-byte nonce || ciphertext from server (AES-GCM ack)
"""
from __future__ import annotations

import logging
import socket
import ssl
import threading

from .config import TlsListenerConfig
from .crypto_session import EncryptedMessage, decrypt, derive_session_key, encrypt
from .framing import recv_frame, send_frame
from .quantum import QRNG_BYTES, generate_quantum_random

logger = logging.getLogger(__name__)


def _build_ssl_context(cfg: TlsListenerConfig) -> ssl.SSLContext:
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=cfg.cert_file, keyfile=cfg.key_file)
    return ctx


def _handle_connection(tls_sock: ssl.SSLSocket, peer: tuple) -> None:
    log = logging.getLogger(f"server01.conn.{peer[0]}:{peer[1]}")
    try:
        # ---- Phase 4: quantum exchange ------------------------------------
        qc = recv_frame(tls_sock)
        if len(qc) != QRNG_BYTES:
            raise ValueError(f"unexpected QC length: {len(qc)}")
        log.info("Received QC (%d bytes)", len(qc))

        qs = generate_quantum_random()
        send_frame(tls_sock, qs)
        log.info("Sent QS (%d bytes)", len(qs))

        # ---- Phase 5: session key ----------------------------------------
        session_key = derive_session_key(qc, qs)
        log.info("Derived SessionKey first 8 bytes: %s", session_key[:8].hex())

        # ---- Phase 6: receive encrypted business message ------------------
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


def serve_forever(cfg: TlsListenerConfig) -> None:
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
                args=(tls_sock, peer),
                name=f"conn-{peer[0]}:{peer[1]}",
                daemon=True,
            )
            t.start()

