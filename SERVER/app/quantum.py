"""Quantum random value generator (PHASE 4 stub) - server side."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

QRNG_BYTES = 32


def generate_quantum_random(num_bytes: int = QRNG_BYTES) -> bytes:
    logger.warning(
        "Using classical os.urandom() as QRNG placeholder (Phase 4 pending)."
    )
    return os.urandom(num_bytes)

