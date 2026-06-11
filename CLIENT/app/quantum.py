"""
Quantum random value generator (PHASE 4 stub).

Real implementation will call an external QRNG service / hardware. For now
this returns a strong classical random value with a clear marker so it is
obvious in logs that the real QRNG hook is still pending.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

QRNG_BYTES = 32  # 256-bit contribution per side


def generate_quantum_random(num_bytes: int = QRNG_BYTES) -> bytes:
    """
    Return ``num_bytes`` of high-entropy bytes.

    TODO(Phase 4): replace os.urandom with a call to the real QRNG provider.
    """
    logger.warning(
        "Using classical os.urandom() as QRNG placeholder (Phase 4 pending). "
        "Replace this with the real QRNG hook before production."
    )
    return os.urandom(num_bytes)

