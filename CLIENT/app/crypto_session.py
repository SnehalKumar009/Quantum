"""
Application-layer session key derivation and message encryption
(PHASES 5 & 6).

    SessionKey = SHA-256( QC || QS )
    Ciphertext = AES-GCM(SessionKey, nonce, plaintext, aad)

Used *inside* the TLS tunnel so that even if TLS were broken, business
payloads remain protected by an independently-derived quantum session key.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def derive_session_key(qc: bytes, qs: bytes) -> bytes:
    """SessionKey = SHA-256(QC || QS) - matches Architecture.md Step 4."""
    digest = hashes.Hash(hashes.SHA256())
    digest.update(qc)
    digest.update(qs)
    return digest.finalize()


@dataclass
class EncryptedMessage:
    nonce: bytes
    ciphertext: bytes


def encrypt(session_key: bytes, plaintext: bytes, aad: bytes = b"") -> EncryptedMessage:
    aes = AESGCM(session_key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext, aad)
    return EncryptedMessage(nonce=nonce, ciphertext=ct)


def decrypt(session_key: bytes, msg: EncryptedMessage, aad: bytes = b"") -> bytes:
    aes = AESGCM(session_key)
    return aes.decrypt(msg.nonce, msg.ciphertext, aad)

