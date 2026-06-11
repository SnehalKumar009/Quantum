"""
RADIUS authentication client.

Uses pyrad to send an Access-Request to radius01 and reports whether the
response was Access-Accept or Access-Reject. This implements Phase 3 of the
architecture: 'Authenticate against RADIUS' before any TLS/quantum work.
"""
from __future__ import annotations

import logging
import socket
from importlib import resources

from pyrad.client import Client
from pyrad.dictionary import Dictionary
from pyrad.packet import AccessAccept, AccessRequest

from .config import RadiusConfig

logger = logging.getLogger(__name__)


def _load_dictionary() -> Dictionary:
    """
    Load a minimal RADIUS dictionary. pyrad ships only the attribute *codes*,
    not the dictionary files themselves, so we write a tiny inline one with
    just the attributes we use.
    """
    # Inline minimal dictionary; sufficient for User-Name / User-Password /
    # NAS-Identifier / Service-Type / Reply-Message.
    return Dictionary(_DICT_PATH())


def _DICT_PATH() -> str:
    """Return path to the bundled dictionary file."""
    # Stored next to this module so it is included in the Docker image.
    import os

    return os.path.join(os.path.dirname(__file__), "radius_dictionary")


class RadiusAuthError(Exception):
    """Raised when RADIUS authentication fails for any reason."""


def authenticate(cfg: RadiusConfig, *, timeout: int = 5) -> bool:
    """
    Send an Access-Request for ``cfg.username`` / ``cfg.password``.

    Returns True on Access-Accept, raises RadiusAuthError on Access-Reject
    or transport errors.
    """
    logger.info(
        "Authenticating as %s against RADIUS %s:%d",
        cfg.username, cfg.host, cfg.auth_port,
    )

    try:
        server_ip = socket.gethostbyname(cfg.host)
    except socket.gaierror as e:
        raise RadiusAuthError(f"Could not resolve RADIUS host {cfg.host!r}: {e}") from e

    client = Client(
        server=server_ip,
        authport=cfg.auth_port,
        secret=cfg.secret,
        dict=_load_dictionary(),
    )
    client.timeout = timeout
    client.retries = 2

    req = client.CreateAuthPacket(
        code=AccessRequest,
        User_Name=cfg.username,
        NAS_Identifier=cfg.nas_identifier,
    )
    req["User-Password"] = req.PwCrypt(cfg.password)

    try:
        reply = client.SendPacket(req)
    except Exception as e:  # pyrad raises plain Exception subclasses
        raise RadiusAuthError(f"RADIUS transport error: {e}") from e

    if reply.code == AccessAccept:
        msg = reply.get("Reply-Message", [""])[0] if "Reply-Message" in reply else ""
        logger.info("Access-Accept received for %s. Reply-Message=%r", cfg.username, msg)
        return True

    raise RadiusAuthError(
        f"Authentication rejected for {cfg.username!r} (code={reply.code})"
    )

