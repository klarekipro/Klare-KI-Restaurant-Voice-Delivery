"""Abstract VoiceProvider contract.

Any future adapter — real SIP + STT + LLM + TTS, or a vendor-specific voice
agent — must implement this interface. The MVP ships a browser simulator
implementation; the server never discloses this to callers in a way that
contradicts the EU AI Act transparency reading (see design/privacy.md §3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass
class CallMeta:
    call_id: str
    language: str = "de-DE"
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    disclosure_at: Optional[str] = None
    human_handover_at: Optional[str] = None
    recording_stored: bool = False
    quality: dict = field(default_factory=dict)


@dataclass
class CapturedItem:
    menu_item_id: int
    name: str
    qty: int
    unit_price_cents: int
    modifiers: str = ""


@dataclass
class CapturedOrder:
    """Payload the voice subsystem hands off to the Order service.

    Mirrors design/voice-ai.md §7.1 schema at the field level.
    """
    customer_phone: str
    customer_name: str
    customer_address: dict
    items: list[CapturedItem]
    call_meta: CallMeta
    customer_id: Optional[int] = None
    crm_match_status: str = "unmatched"
    delivery_notes: str = ""


class VoiceProvider(Protocol):
    """Boundary between the voice subsystem and the rest of the system."""

    name: str

    def start_call(self, caller_phone: Optional[str]) -> CallMeta: ...
    def end_call(self, call_id: str) -> None: ...
    # The MVP's "capture" step is driven by the simulator UI below; real
    # providers would stream ASR partials, drive dialog turns, etc.
