"""
qconnect - simulated RNG / key-distribution service.

Endpoints:
    POST /keys/generate     -> generate a fresh KeyId/Key, persist to disk,
                                return JSON { "KeyId": ..., "Key": ... }
    GET  /keys              -> list all stored KeyIds
    GET  /keys/{key_id}     -> fetch a previously generated key
    DELETE /keys/{key_id}   -> delete a key
    GET  /healthz           -> liveness

Storage:
    One JSON file per key under $QCONNECT_DATA_DIR (default /data/keys).
    Filename = <KeyId>.json. Persisted via a Docker named volume.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("QCONNECT_DATA_DIR", "/data/keys"))
KEY_BYTES = int(os.environ.get("KEY_BYTES", "32"))   # 256-bit keys
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("qconnect")

DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="QConnect", description="Lab RNG / key-distribution service")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class KeyRecord(BaseModel):
    KeyId: str
    Key: str        # hex-encoded


class KeyList(BaseModel):
    count: int
    keys: List[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _path_for(key_id: str) -> Path:
    # Strict validation: only allow safe characters in key_id (prevent traversal)
    safe = "".join(c for c in key_id if c.isalnum() or c in "-_")
    if safe != key_id or not safe:
        raise HTTPException(status_code=400, detail="invalid KeyId")
    return DATA_DIR / f"{safe}.json"


def _new_key_id() -> str:
    return f"qkey-{uuid.uuid4().hex[:12]}"


def _new_key_hex() -> str:
    return secrets.token_hex(KEY_BYTES)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/keys/generate", response_model=KeyRecord, status_code=201)
def generate_key():
    rec = KeyRecord(KeyId=_new_key_id(), Key=_new_key_hex())
    path = _path_for(rec.KeyId)
    path.write_text(rec.model_dump_json(), encoding="utf-8")
    log.info("Generated key %s (%d bytes)", rec.KeyId, KEY_BYTES)
    return rec


@app.get("/keys", response_model=KeyList)
def list_keys():
    ids = sorted(p.stem for p in DATA_DIR.glob("*.json"))
    return KeyList(count=len(ids), keys=ids)


@app.get("/keys/{key_id}", response_model=KeyRecord)
def get_key(key_id: str):
    path = _path_for(key_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"KeyId {key_id} not found")
    try:
        return KeyRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.exception("Failed to read key %s", key_id)
        raise HTTPException(status_code=500, detail=f"corrupt key file: {e}")


@app.delete("/keys/{key_id}", status_code=204)
def delete_key(key_id: str):
    path = _path_for(key_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"KeyId {key_id} not found")
    path.unlink()
    log.info("Deleted key %s", key_id)
    return JSONResponse(status_code=204, content=None)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "data_dir": str(DATA_DIR), "key_bytes": KEY_BYTES}

