"""
NAS (radius-client) HTTP client.

Replaces the previous direct-pyrad RADIUS authentication. We POST four
fields to the NAS and let it speak RADIUS upstream:

    POST {nas_url}/auth
    Authorization: Bearer {nas_shared_token}
    { "username", "password", "KeyId", "Key" }
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

from .config import IdentityConfig, NasConfig

logger = logging.getLogger(__name__)


class NasAuthError(Exception):
    """Raised on Access-Reject, NAS error, or transport failure."""


def authenticate(
    nas: NasConfig,
    identity: IdentityConfig,
    key_id: str,
    key_hex: str,
    *,
    timeout: float = 10.0,
) -> str:
    """
    Returns the server's Reply-Message on success, raises NasAuthError otherwise.
    """
    url = f"{nas.url}/auth"
    headers = {"Content-Type": "application/json"}
    if nas.shared_token:
        headers["Authorization"] = f"Bearer {nas.shared_token}"

    payload = {
        "username": identity.username,
        "password": identity.password,
        "KeyId": key_id,
        "Key": key_hex,
    }

    logger.info("Authenticating via NAS %s as %s (KeyId=%s)",
                url, identity.username, key_id)

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise NasAuthError(f"NAS unreachable: {e}") from e

    if r.status_code == 200:
        try:
            body = r.json()
        except ValueError:
            body = {}
        reply_message = body.get("reply_message", "")
        logger.info("NAS auth OK for %s. Reply-Message=%r",
                    identity.username, reply_message)
        return reply_message

    # Any non-200 is failure. 401 = Access-Reject or bad NAS token.
    raise NasAuthError(
        f"NAS auth failed (HTTP {r.status_code}): {_safe_body(r)}"
    )


def _safe_body(r: requests.Response) -> str:
    try:
        return r.json()
    except ValueError:
        return r.text

