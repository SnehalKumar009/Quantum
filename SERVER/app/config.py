"""
Runtime configuration for server01.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


def _env(name: str, default: Optional[str] = None, *, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val  # type: ignore[return-value]


@dataclass(frozen=True)
class RadiusConfig:
    host: str
    auth_port: int
    secret: bytes
    username: str
    password: str
    nas_identifier: str


@dataclass(frozen=True)
class TlsListenerConfig:
    host: str
    port: int
    cert_file: str
    key_file: str


@dataclass(frozen=True)
class AppConfig:
    radius: RadiusConfig
    listener: TlsListenerConfig
    log_level: str


def load_config() -> AppConfig:
    cert_dir = _env("CERT_DIR", "/app/certs")
    return AppConfig(
        radius=RadiusConfig(
            host=_env("RADIUS_HOST", "radius01"),
            auth_port=int(_env("RADIUS_AUTH_PORT", "1812")),
            secret=_env("RADIUS_SECRET", "testing123").encode("utf-8"),
            username=_env("RADIUS_USERNAME", "server01"),
            password=_env("RADIUS_PASSWORD", "serverPassword"),
            nas_identifier=_env("RADIUS_NAS_IDENTIFIER", "server01"),
        ),
        listener=TlsListenerConfig(
            host=_env("LISTEN_HOST", "0.0.0.0"),
            port=int(_env("LISTEN_PORT", "8443")),
            cert_file=os.path.join(cert_dir, "server.crt"),
            key_file=os.path.join(cert_dir, "server.key"),
        ),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
    )

