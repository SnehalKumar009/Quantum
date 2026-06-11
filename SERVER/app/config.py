"""Runtime configuration for server01."""
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
class IdentityConfig:
    username: str
    password: str


@dataclass(frozen=True)
class NasConfig:
    url: str
    shared_token: str


@dataclass(frozen=True)
class QConnectConfig:
    url: str


@dataclass(frozen=True)
class TlsListenerConfig:
    host: str
    port: int
    cert_file: str
    key_file: str


@dataclass(frozen=True)
class AppConfig:
    identity: IdentityConfig
    nas: NasConfig
    qconnect: QConnectConfig
    listener: TlsListenerConfig
    log_level: str


def load_config() -> AppConfig:
    cert_dir = _env("CERT_DIR", "/app/certs")
    return AppConfig(
        identity=IdentityConfig(
            username=_env("USERNAME", "server01"),
            password=_env("PASSWORD", "serverPassword"),
        ),
        nas=NasConfig(
            url=_env("NAS_URL", "http://radius-client:8082").rstrip("/"),
            shared_token=_env("NAS_SHARED_TOKEN", "lab-nas-token"),
        ),
        qconnect=QConnectConfig(
            url=_env("QCONNECT_URL", "http://qconnect:9000").rstrip("/"),
        ),
        listener=TlsListenerConfig(
            host=_env("LISTEN_HOST", "0.0.0.0"),
            port=int(_env("LISTEN_PORT", "8443")),
            cert_file=os.path.join(cert_dir, "server.crt"),
            key_file=os.path.join(cert_dir, "server.key"),
        ),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
    )

