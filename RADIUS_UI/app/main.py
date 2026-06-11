"""
radius-ui - tiny FastAPI app exposing two things:

  GET  /        -> page with list of known accounts and a test form
  POST /test    -> send Access-Request to radius01 and show the result

No DB. The "known accounts" list is parsed from the same `authorize` file
that FreeRADIUS uses, mounted read-only into this container.
"""
from __future__ import annotations

import os
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pyrad.client import Client
from pyrad.dictionary import Dictionary
from pyrad.packet import AccessAccept, AccessRequest, AccessReject

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RADIUS_HOST = os.environ.get("RADIUS_HOST", "radius01")
RADIUS_AUTH_PORT = int(os.environ.get("RADIUS_AUTH_PORT", "1812"))
RADIUS_SECRET = os.environ.get("RADIUS_SECRET", "testing123").encode()
AUTHORIZE_FILE = Path(os.environ.get(
    "AUTHORIZE_FILE",
    "/raddb/mods-config/files/authorize",
))
DICT_PATH = Path(__file__).with_name("radius_dictionary")

app = FastAPI(title="Quantum Lab - RADIUS UI")
templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@dataclass
class Account:
    username: str
    has_password: bool


_USER_LINE = re.compile(r'^\s*([A-Za-z0-9_.\-]+)\s+Cleartext-Password\s*:=\s*"([^"]*)"')


def load_accounts() -> list[Account]:
    """Parse the authorize file for `<user> Cleartext-Password := "..."`."""
    if not AUTHORIZE_FILE.exists():
        return []
    accounts: list[Account] = []
    for line in AUTHORIZE_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _USER_LINE.match(line)
        if m:
            accounts.append(Account(username=m.group(1), has_password=bool(m.group(2))))
    return accounts


@dataclass
class TestResult:
    ok: bool
    code_label: str
    message: str
    username: str


def send_access_request(username: str, password: str) -> TestResult:
    try:
        server_ip = socket.gethostbyname(RADIUS_HOST)
    except socket.gaierror as e:
        return TestResult(False, "DNS error", f"Cannot resolve {RADIUS_HOST!r}: {e}", username)

    client = Client(
        server=server_ip,
        authport=RADIUS_AUTH_PORT,
        secret=RADIUS_SECRET,
        dict=Dictionary(str(DICT_PATH)),
    )
    client.timeout = 5
    client.retries = 2

    req = client.CreateAuthPacket(
        code=AccessRequest,
        User_Name=username,
        NAS_Identifier="radius-ui",
    )
    req["User-Password"] = req.PwCrypt(password)

    try:
        reply = client.SendPacket(req)
    except Exception as e:
        return TestResult(False, "Transport error", str(e), username)

    if reply.code == AccessAccept:
        rmsg = reply.get("Reply-Message", [""])[0] if "Reply-Message" in reply else ""
        return TestResult(True, "Access-Accept", rmsg or "(no Reply-Message)", username)
    if reply.code == AccessReject:
        return TestResult(False, "Access-Reject", "Server rejected the credentials.", username)
    return TestResult(False, f"Unexpected code {reply.code}", "", username)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index(request: Request,
          username: Optional[str] = None,
          result_ok: Optional[bool] = None,
          result_code: Optional[str] = None,
          result_msg: Optional[str] = None):
    result = None
    if username is not None:
        result = TestResult(
            ok=bool(result_ok),
            code_label=result_code or "",
            message=result_msg or "",
            username=username,
        )
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "accounts": load_accounts(),
            "radius_host": RADIUS_HOST,
            "radius_port": RADIUS_AUTH_PORT,
            "result": result,
        },
    )


@app.post("/test", response_class=HTMLResponse)
def test_auth(request: Request,
              username: str = Form(...),
              password: str = Form(...)):
    res = send_access_request(username, password)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "accounts": load_accounts(),
            "radius_host": RADIUS_HOST,
            "radius_port": RADIUS_AUTH_PORT,
            "result": res,
            "submitted_username": username,
        },
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok"}

