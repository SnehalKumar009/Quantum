"""
RADIUS authentication client (same logic as client01's module).

server01 also has to authenticate itself to radius01 on startup, per
Architecture.md "Server Authentication" flow.
"""
from __future__ import annotations

import logging
import os
import socket

from pyrad.client import Client
from pyrad.dictionary import Dictionary
from pyrad.packet import AccessAccept, AccessRequest

from .config import RadiusConfig

logger = logging.getLogger(__name__)


def _dict_path() -> str:
    return os.path.join(os.path.dirname(__file__), "radius_dictionary")


class RadiusAuthError(Exception):
    """Raised when RADIUS authentication fails."""


def authenticate(cfg: RadiusConfig, *, timeout: int = 5) -> bool:
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
        dict=Dictionary(_dict_path()),
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
    except Exception as e:
        raise RadiusAuthError(f"RADIUS transport error: {e}") from e

    if reply.code == AccessAccept:
        msg = reply.get("Reply-Message", [""])[0] if "Reply-Message" in reply else ""
        logger.info("Access-Accept received for %s. Reply-Message=%r", cfg.username, msg)
        return True

    raise RadiusAuthError(
        f"Authentication rejected for {cfg.username!r} (code={reply.code})"
    )

