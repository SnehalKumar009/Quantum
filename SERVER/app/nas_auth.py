"""NAS (radius-client) HTTP client for server01."""
from __future__ import annotations

import logging
import os

import requests

from .config import IdentityConfig, NasConfig

logger = logging.getLogger(__name__)

# Must exceed the NAS-side PRE_AUTH_DELAY_SECONDS.
NAS_HTTP_TIMEOUT = float(os.environ.get("NAS_HTTP_TIMEOUT", "120"))


class NasAuthError(Exception):
    pass


def authenticate(
    nas: NasConfig,
    identity: IdentityConfig,
    key_id: str,
    key_hex: str,
    *,
    timeout: float = NAS_HTTP_TIMEOUT,
) -> str:
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

    logger.info("Authenticating via NAS %s as %s (KeyId=%s Key=%s)",
                url, identity.username, key_id, key_hex)

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise NasAuthError(f"NAS unreachable: {e}") from e

    if r.status_code == 200:
        body = {}
        try:
            body = r.json()
        except ValueError:
            pass
        reply_message = body.get("reply_message", "")
        logger.info("NAS auth OK for %s. Reply-Message=%r",
                    identity.username, reply_message)
        return reply_message

    raise NasAuthError(f"NAS auth failed (HTTP {r.status_code}): {r.text}")

