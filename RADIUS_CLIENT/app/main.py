"""
radius-client (NAS) — accepts HTTP /auth from supplicants, forwards as a
RADIUS Access-Request to radius01.

Supplicants send four fields:
    { "username": "...", "password": "...", "KeyId": "...", "Key": "..." }

These are mapped onto RADIUS attributes:
    User-Name          -> username
    User-Password      -> password (encrypted with the shared RADIUS secret)
    Quantum-Key-Id     -> KeyId   (Vendor-Specific, vendor 99999, attr 1)
    Quantum-Key        -> Key     (Vendor-Specific, vendor 99999, attr 2)

The RADIUS server today authenticates on username/password only; the VSAs
are transported and logged, ready for future policy.
"""
from __future__ import annotations

import logging
import os
import socket
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from pyrad.client import Client
from pyrad.dictionary import Dictionary
from pyrad.packet import AccessAccept, AccessReject, AccessRequest

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RADIUS_HOST       = os.environ.get("RADIUS_HOST", "radius01")
RADIUS_AUTH_PORT  = int(os.environ.get("RADIUS_AUTH_PORT", "1812"))
RADIUS_SECRET     = os.environ.get("RADIUS_SECRET", "testing123").encode()
NAS_IDENTIFIER    = os.environ.get("NAS_IDENTIFIER", "radius-client-01")
NAS_SHARED_TOKEN  = os.environ.get("NAS_SHARED_TOKEN", "lab-nas-token")
LOG_LEVEL         = os.environ.get("LOG_LEVEL", "INFO").upper()


DICT_PATH = Path(__file__).with_name("radius_dictionary")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("radius-client")

app = FastAPI(title="radius-client",
              description="NAS — HTTP /auth → RADIUS Access-Request")


# ---------------------------------------------------------------------------
# Auth dependency (shared token between supplicant and NAS)
# ---------------------------------------------------------------------------
def require_nas_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not NAS_SHARED_TOKEN:
        return  # auth disabled
    expected = f"Bearer {NAS_SHARED_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="invalid NAS token")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class AuthRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)
    KeyId: str = Field(min_length=1, max_length=128)
    Key:   str = Field(min_length=1, max_length=512)


class AuthResponse(BaseModel):
    ok: bool
    reply_message: str = ""
    reason: str = ""


# ---------------------------------------------------------------------------
# RADIUS plumbing
# ---------------------------------------------------------------------------
def _radius_client() -> Client:
    try:
        server_ip = socket.gethostbyname(RADIUS_HOST)
    except socket.gaierror as e:
        raise HTTPException(status_code=502,
                            detail=f"cannot resolve {RADIUS_HOST!r}: {e}") from e
    c = Client(server=server_ip, authport=RADIUS_AUTH_PORT,
               secret=RADIUS_SECRET, dict=Dictionary(str(DICT_PATH)))
    c.timeout = 5
    c.retries = 2
    return c


def _send_access_request(req_body: AuthRequest) -> AuthResponse:
    client = _radius_client()

    req = client.CreateAuthPacket(
        code=AccessRequest,
        User_Name=req_body.username,
        NAS_Identifier=NAS_IDENTIFIER,
    )
    req["User-Password"] = req.PwCrypt(req_body.password)
    # VSAs from the Quantum-Lab vendor dictionary.
    req["Quantum-Key-Id"] = req_body.KeyId
    req["Quantum-Key"]    = req_body.Key

    log.info(
        "Forwarding Access-Request: user=%s KeyId=%s Key=%s (len=%d) -> %s:%d",
        req_body.username, req_body.KeyId, req_body.Key, len(req_body.Key),
        RADIUS_HOST, RADIUS_AUTH_PORT,
    )


    try:
        reply = client.SendPacket(req)
    except Exception as e:
        log.warning("RADIUS transport error for user=%s: %s", req_body.username, e)
        raise HTTPException(status_code=502,
                            detail=f"RADIUS transport error: {e}") from e

    if reply.code == AccessAccept:
        rmsg = reply.get("Reply-Message", [""])[0] if "Reply-Message" in reply else ""
        log.info("Access-Accept for user=%s reply_message=%r", req_body.username, rmsg)
        return AuthResponse(ok=True, reply_message=rmsg)
    if reply.code == AccessReject:
        rmsg = reply.get("Reply-Message", [""])[0] if "Reply-Message" in reply else ""
        log.info("Access-Reject for user=%s reply_message=%r", req_body.username, rmsg)
        return AuthResponse(ok=False, reply_message=rmsg,
                            reason=f"Access-Reject: {rmsg}" if rmsg else "Access-Reject")
    log.warning("Unexpected RADIUS reply code=%s for user=%s", reply.code, req_body.username)
    return AuthResponse(ok=False, reason=f"unexpected RADIUS code {reply.code}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/auth", response_model=AuthResponse,
          dependencies=[Depends(require_nas_token)])
def auth(req: AuthRequest):
    result = _send_access_request(req)
    if not result.ok:
        # Use 401 for Reject so curl/HTTP clients can easily tell.
        raise HTTPException(status_code=401, detail=result.model_dump())
    return result


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "radius_target": f"{RADIUS_HOST}:{RADIUS_AUTH_PORT}",
        "nas_identifier": NAS_IDENTIFIER,
        "token_required": bool(NAS_SHARED_TOKEN),
    }

