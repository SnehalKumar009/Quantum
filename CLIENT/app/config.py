"""
Runtime configuration for client01.

All settings come from environment variables so the same image runs unchanged
across phases of the lab (single host, multi-host, prod).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None, *, required: bool = False) -> str:
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
class ServerConfig:
    host: str
    port: int


@dataclass(frozen=True)
class AppConfig:
    radius: RadiusConfig
    server: ServerConfig
    log_level: str


def load_config() -> AppConfig:
    return AppConfig(
        radius=RadiusConfig(
            host=_env("RADIUS_HOST", "radius01"),
            auth_port=int(_env("RADIUS_AUTH_PORT", "1812")),
            secret=_env("RADIUS_SECRET", "testing123").encode("utf-8"),
            username=_env("RADIUS_USERNAME", "client01"),
            password=_env("RADIUS_PASSWORD", "clientPassword"),
            nas_identifier=_env("RADIUS_NAS_IDENTIFIER", "client01"),
        ),
        server=ServerConfig(
            host=_env("SERVER_HOST", "server01"),
            port=int(_env("SERVER_PORT", "8443")),
        ),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
    )

