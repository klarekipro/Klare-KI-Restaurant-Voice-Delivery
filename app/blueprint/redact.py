"""Server-side regex redactor for Blueprint free-text fields.

Mitigates the risk that `notes` fields accumulate PII (phone numbers, email
addresses, IBAN prefixes) even when the UI already warns the user. The redactor
returns the sanitized text and a list of pattern labels that fired, so the
caller can write a single audit entry (`blueprint.notes.redacted`) without
putting the original content into the log.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_NOTES_LENGTH = 500

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("iban",  re.compile(r"\bDE\d{2}[\s\d]{10,}\b")),
    # Phone: a leading digit or '+' followed by at least 6 more digits (with
    # optional spaces, dashes, slashes). We require at least 7 digits total to
    # avoid matching short numeric fragments like prices or quantities.
    ("phone", re.compile(r"(?:\+?\d[\d\s/\-]{6,})")),
)


@dataclass(frozen=True)
class RedactionResult:
    text: str
    hits: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return bool(self.hits)


def redact(raw: str) -> RedactionResult:
    """Return `(redacted_text, hits)` for a user-supplied free-text string."""
    text = (raw or "").strip()
    if len(text) > MAX_NOTES_LENGTH:
        text = text[:MAX_NOTES_LENGTH]
    hits: list[str] = []
    for label, pattern in _PATTERNS:
        if pattern.search(text):
            # Only count the phone pattern if it actually matched >= 7 digits.
            if label == "phone":
                found = pattern.findall(text)
                if not any(sum(ch.isdigit() for ch in m) >= 7 for m in found):
                    continue
            text = pattern.sub(f"[REDACTED:{label}]", text)
            hits.append(label)
    return RedactionResult(text=text, hits=tuple(hits))
