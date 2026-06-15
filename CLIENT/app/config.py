"""
Runtime configuration for client01.

All settings come from environment variables.
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
class IdentityConfig:
    """Who we are when authenticating."""
    username: str
    password: str


@dataclass(frozen=True)
class NasConfig:
    """How we talk to the radius-client (NAS)."""
    url: str
    shared_token: str


@dataclass(frozen=True)
class QConnectConfig:
    """How we talk to QConnect for our session key registration."""
    url: str


@dataclass(frozen=True)
class QkdConfig:
    """Real qConnect KME settings (ETSI GS QKD 014, mTLS)."""
    kme_url: str
    cert_file: str
    key_file: str
    ca_file: str
    info_json: str
    peer_sae_id: str       # slave SAE this client requests keys for (radius01)
    sae_id: str            # optional override; usually derived from info.json
    # Data-plane peer (the server this client will exchange a QKD-derived
    # session key with on every TLS connection). For client01 this is
    # server01's SAE UUID. Distinct from peer_sae_id (radius01, auth-plane).
    data_peer_sae_id: str


@dataclass(frozen=True)
class ServerConfig:
    """Where server01 lives (TLS application target)."""
    host: str
    port: int


@dataclass(frozen=True)
class AppConfig:
    identity: IdentityConfig
    nas: NasConfig
    qconnect: QConnectConfig
    qkd: QkdConfig
    server: ServerConfig
    log_level: str


def load_config() -> AppConfig:
    return AppConfig(
        identity=IdentityConfig(
            username=_env("USERNAME", "client01"),
            password=_env("PASSWORD", "clientPassword"),
        ),
        nas=NasConfig(
            url=_env("NAS_URL", "http://radius-client:8082").rstrip("/"),
            shared_token=_env("NAS_SHARED_TOKEN", "lab-nas-token"),
        ),
        qconnect=QConnectConfig(
            url=_env("QCONNECT_URL", "http://qconnect:9000").rstrip("/"),
        ),
        qkd=QkdConfig(
            kme_url=_env("QKD_KME_URL", "").rstrip("/"),
            cert_file=_env("QKD_CERT",   "/etc/qkd/sae-client01.crt.pem"),
            key_file=_env("QKD_KEY",     "/etc/qkd/sae-client01.key.pem"),
            ca_file=_env("QKD_CACERT",   "/etc/qkd/sae-client01.trusted_cas.pem"),
            info_json=_env("QKD_INFO_JSON", "/etc/qkd/sae-client01.info.json"),
            peer_sae_id=_env("QKD_PEER_SAE_ID", ""),
            sae_id=_env("QKD_SAE_ID", ""),
            data_peer_sae_id=_env("QKD_DATA_PEER_SAE_ID", ""),
        ),
        server=ServerConfig(
            host=_env("SERVER_HOST", "server01"),
            port=int(_env("SERVER_PORT", "8443")),
        ),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
    )

