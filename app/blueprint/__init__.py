"""Klare KI Restaurant Blueprint: Demo + Diagnose + Vorschlag.

The Blueprint package adds a demonstration-and-diagnostic surface on top of the
existing restaurant MVP. It does not replace or alter existing modules.
"""
from .routes import router

__all__ = ["router"]
