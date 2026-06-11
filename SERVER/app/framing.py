"""
Length-prefixed framing over a stream socket.

Wire format for every frame:
    [4 bytes big-endian length N][N bytes payload]

Used inside the TLS tunnel so we don't have to invent a parser.
Identical copy lives in client01/app/framing.py.
"""
from __future__ import annotations

import socket
import struct

_LEN = struct.Struct(">I")
MAX_FRAME = 1 << 20  # 1 MiB safety cap


def send_frame(sock: socket.socket, payload: bytes) -> None:
    if len(payload) > MAX_FRAME:
        raise ValueError(f"frame too large: {len(payload)}")
    sock.sendall(_LEN.pack(len(payload)) + payload)


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed during recv_exact")
        buf.extend(chunk)
    return bytes(buf)


def recv_frame(sock: socket.socket) -> bytes:
    (length,) = _LEN.unpack(recv_exact(sock, 4))
    if length > MAX_FRAME:
        raise ValueError(f"frame too large: {length}")
    return recv_exact(sock, length)

