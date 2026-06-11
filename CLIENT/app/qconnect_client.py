"""
QConnect HTTP client.

On boot the supplicant calls POST /keys/generate to register itself and
obtain a fresh (KeyId, Key) pair that it will later include in the
authentication request to the NAS.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from .config import QConnectConfig

logger = logging.getLogger(__name__)


class QConnectError(Exception):
    """Raised when QConnect cannot be reached or returns an unexpected body."""


@dataclass(frozen=True)
class KeyRecord:
    key_id: str
    key: str        # hex-encoded


def register(cfg: QConnectConfig, *, timeout: float = 5.0) -> KeyRecord:
    """POST /keys/generate -> KeyRecord. Raises QConnectError on failure."""
    url = f"{cfg.url}/keys/generate"
    logger.info("Registering with QConnect at %s", url)
    try:
        r = requests.post(url, timeout=timeout)
    except requests.RequestException as e:
        raise QConnectError(f"QConnect unreachable: {e}") from e

    if r.status_code not in (200, 201):
        raise QConnectError(f"QConnect returned HTTP {r.status_code}: {r.text}")

    try:
        body = r.json()
        rec = KeyRecord(key_id=body["KeyId"], key=body["Key"])
    except (ValueError, KeyError, TypeError) as e:
        raise QConnectError(f"unexpected QConnect body: {r.text!r}") from e

    logger.info("Registered with QConnect: KeyId=%s (%d-char hex key)",
                rec.key_id, len(rec.key))
    return rec

