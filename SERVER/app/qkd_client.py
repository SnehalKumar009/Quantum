"""
ETSI GS QKD 014 client for server01.

Talks to the qConnect KME over mTLS:

    status(peer_sae_id)   -> GET /api/v1/keys/{peer}/status
    enc_key(peer_sae_id)  -> GET /api/v1/keys/{peer}/enc_keys     (master role)
    dec_key(master, kid)  -> GET /api/v1/keys/{master}/dec_keys?key_ID=kid
                            (kept for completeness; not used by server01)

Each call uses the SAE's client cert + key + CA bundle bind-mounted at
/etc/qkd by the docker-compose volume.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import requests

from .config import QkdConfig

logger = logging.getLogger(__name__)


class QkdError(Exception):
    """Raised for any failure talking to the KME."""


@dataclass(frozen=True)
class QkdKey:
    key_id: str
    key: str  # base64 of the raw key bytes (as returned by the KME)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _check_files(cfg: QkdConfig) -> None:
    for label, path in (
        ("QKD_CERT",   cfg.cert_file),
        ("QKD_KEY",    cfg.key_file),
        ("QKD_CACERT", cfg.ca_file),
    ):
        if not path or not Path(path).is_file():
            raise QkdError(f"{label} unreadable: {path!r}")


def _get(cfg: QkdConfig, url: str, *, timeout: float = 5.0) -> dict:
    _check_files(cfg)
    logger.info("qkd GET %s", url)
    try:
        r = requests.get(
            url,
            cert=(cfg.cert_file, cfg.key_file),
            verify=cfg.ca_file,
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise QkdError(f"KME unreachable: {e}") from e

    logger.info("qkd HTTP %s  body=%s", r.status_code, r.text[:400])

    if r.status_code != 200:
        raise QkdError(f"KME returned HTTP {r.status_code}: {r.text}")
    try:
        return r.json()
    except ValueError as e:
        raise QkdError(f"KME body is not JSON: {r.text!r}") from e


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def own_sae_id(cfg: QkdConfig) -> str:
    """Read this SAE's own UUID out of the bundle's info.json."""
    if cfg.sae_id:        # env override wins (kept for tests)
        return cfg.sae_id
    if not cfg.info_json or not Path(cfg.info_json).is_file():
        raise QkdError(f"QKD_INFO_JSON unreadable: {cfg.info_json!r}")
    try:
        data = json.loads(Path(cfg.info_json).read_text())
        sae_id = data["sae_id"]
    except (OSError, ValueError, KeyError) as e:
        raise QkdError(f"cannot read sae_id from {cfg.info_json}: {e}") from e
    if not sae_id:
        raise QkdError(f"sae_id field is empty in {cfg.info_json}")
    return sae_id


def status(cfg: QkdConfig, peer_sae_id: str) -> dict:
    url = f"{cfg.kme_url.rstrip('/')}/api/v1/keys/{peer_sae_id}/status"
    return _get(cfg, url)


def enc_key(cfg: QkdConfig, peer_sae_id: str) -> QkdKey:
    """Master role: ask the KME for one fresh key destined for peer_sae_id."""
    if not peer_sae_id:
        raise QkdError("peer SAE ID is empty (set QKD_PEER_SAE_ID in env)")
    url = f"{cfg.kme_url.rstrip('/')}/api/v1/keys/{peer_sae_id}/enc_keys"
    logger.info("[TRACE enc_key] REQ  master=self  slave=%s  url=%s",
                peer_sae_id, url)
    body = _get(cfg, url)
    logger.info("[TRACE enc_key] RESP body=%s", body)
    try:
        first = body["keys"][0]
        rec = QkdKey(key_id=first["key_ID"], key=first["key"])
    except (KeyError, IndexError, TypeError) as e:
        raise QkdError(f"unexpected enc_keys body: {body!r}") from e
    logger.info(
        "[TRACE enc_key] OK   key_id=%s  key_b64=%s  (b64_len=%d)",
        rec.key_id, rec.key, len(rec.key),
    )
    return rec


def dec_key(cfg: QkdConfig, master_sae_id: str, key_id: str) -> QkdKey:
    """Slave role: retrieve a previously-issued key by id."""
    url = (
        f"{cfg.kme_url.rstrip('/')}/api/v1/keys/{master_sae_id}"
        f"/dec_keys?key_ID={key_id}"
    )
    logger.info("[TRACE dec_key] REQ  master=%s  slave=self  key_id=%s  url=%s",
                master_sae_id, key_id, url)
    body = _get(cfg, url)
    logger.info("[TRACE dec_key] RESP body=%s", body)
    try:
        first = body["keys"][0]
        rec = QkdKey(key_id=first["key_ID"], key=first["key"])
    except (KeyError, IndexError, TypeError) as e:
        raise QkdError(f"unexpected dec_keys body: {body!r}") from e
    logger.info(
        "[TRACE dec_key] OK   key_id=%s  key_b64=%s  (b64_len=%d)",
        rec.key_id, rec.key, len(rec.key),
    )
    return rec

