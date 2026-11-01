# Voice-Integration — Anleitung

Dieses MVP nutzt einen **Browser-Simulator** (`app/voice/simulator.py`) anstelle einer echten Telefonie-Pipeline. Die Grenze ist bewusst durch `app/voice/interface.py` abgedichtet, damit jede reale Implementierung ohne Änderungen am Order-Service eingehängt werden kann.

## Vertrag

Jede neue `VoiceProvider`-Implementierung muss:

1. `start_call(caller_phone)` liefern `CallMeta` mit mindestens `call_id` und `started_at`.
2. Beim Abschluss der Bestellung ein `CapturedOrder`-Objekt an den Order-Service weitergeben (`app/main.py:_submit_call_payload` ist der Referenzsenke).
3. `end_call(call_id)` aufrufen, bevor der Dialog beendet wird.

Die Payload-Form (CRM-Felder, Items mit `menu_item_id`, `qty`, Modifier) ist in `design/voice-ai.md §7.1` festgehalten.

## Hard-Defaults, die der Provider respektieren MUSS

- `recording_stored = False` (ADR-P-03 / ADR-V8).
- EU-AI-Act-Transparenz vor dem ersten inhaltlichen Austausch (ADR-V13 / ADR-P-12).
- Verbale Namens-Prüfung, bevor eine gespeicherte Adresse am Telefon vorgelesen wird (ADR-V11 / ADR-P-06, Guard R-B).
- DE-primär; Fallback-Pfad zur menschlichen Übergabe.

## Beispielhafter Integrationspfad (ohne Code hier)

1. Telefonie-Trunk (SIP) + Media-Server bereitstellen (EU-Hosting).
2. Streaming-STT für `de-DE` anbinden (`Candidate (verify):` lokal gehostet oder EU-Vendor).
3. Dialog-Manager + LLM mit Function-Calling nach dem Order-Schema (`design/voice-ai.md §6` Archetyp C).
4. Streaming-TTS für `de-DE` mit SSML-Aussprache-Hinweisen (siehe Menü-Lexikon).
5. Umsetzung des DPIA/TOM-Pakets aus `design/privacy.md §7–9`.

Dieser Pfad erfordert ADR-Entscheidungen, DPA-Verträge und Rechts-Review. **Keine Produktion ohne Legal + PO.**

## Testbetrieb ohne echten Provider

Der Simulator bleibt der kostenfreie Testmodus. Er ist in der UI explizit markiert und kann für Rollenschulungen, Datenfluss-Reviews und E2E-Tests genutzt werden.
