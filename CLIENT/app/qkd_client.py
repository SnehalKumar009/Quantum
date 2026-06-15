"""
ETSI GS QKD 014 client for client01.

Mirrors SERVER/app/qkd_client.py — duplicated so each component stays a
self-contained build context. See that file for the full design notes.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import QkdConfig

logger = logging.getLogger(__name__)


class QkdError(Exception):
    pass


@dataclass(frozen=True)
class QkdKey:
    key_id: str
    key: str   # base64 of the raw key bytes, as returned by the KME


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


def own_sae_id(cfg: QkdConfig) -> str:
    if cfg.sae_id:
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
    return _get(cfg, f"{cfg.kme_url.rstrip('/')}/api/v1/keys/{peer_sae_id}/status")


def enc_key(cfg: QkdConfig, peer_sae_id: str) -> QkdKey:
    if not peer_sae_id:
        raise QkdError("peer SAE ID is empty (set QKD_PEER_SAE_ID in env)")
    url = f"{cfg.kme_url.rstrip('/')}/api/v1/keys/{peer_sae_id}/enc_keys"
    body = _get(cfg, url)
    try:
        first = body["keys"][0]
        rec = QkdKey(key_id=first["key_ID"], key=first["key"])
    except (KeyError, IndexError, TypeError) as e:
        raise QkdError(f"unexpected enc_keys body: {body!r}") from e
    logger.info("enc_keys OK  key_id=%s  key_len=%d", rec.key_id, len(rec.key))
    return rec


def dec_key(cfg: QkdConfig, master_sae_id: str, key_id: str) -> QkdKey:
    url = (
        f"{cfg.kme_url.rstrip('/')}/api/v1/keys/{master_sae_id}"
        f"/dec_keys?key_ID={key_id}"
    )
    body = _get(cfg, url)
    try:
        first = body["keys"][0]
        return QkdKey(key_id=first["key_ID"], key=first["key"])
    except (KeyError, IndexError, TypeError) as e:
        raise QkdError(f"unexpected dec_keys body: {body!r}") from e

