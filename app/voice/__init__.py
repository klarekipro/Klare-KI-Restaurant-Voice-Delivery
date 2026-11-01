"""Voice subsystem — isolated interface + in-browser simulator provider.

The real telephony provider is intentionally NOT bundled. See
`app/voice/interface.py` for the contract any future SIP/ASR/LLM/TTS adapter
must satisfy, and `docs/voice-integration.md` for the integration guide.
"""
