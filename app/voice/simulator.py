"""In-browser call simulator.

This simulator does NOT make real phone calls. It mimics the voice subsystem's
output contract (CapturedOrder) so the rest of the system can be exercised end
to end. A real telephony provider plugs into the same seam without changing
the Order service.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from .interface import CallMeta


class SimulatorVoiceProvider:
    """Minimal VoiceProvider implementation for the MVP."""

    name = "browser-simulator"

    def start_call(self, caller_phone: Optional[str]) -> CallMeta:
        return CallMeta(
            call_id="sim-" + uuid.uuid4().hex[:12],
            language="de-DE",
            started_at=datetime.utcnow().replace(microsecond=0).isoformat(" "),
            disclosure_at=datetime.utcnow().replace(microsecond=0).isoformat(" "),
            recording_stored=False,
            quality={"provider": "browser-simulator"},
        )

    def end_call(self, call_id: str) -> None:
        return None
