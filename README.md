# Klare KI — Restaurant Voice & Delivery MVP

> **Portfolio-Kurzüberblick:** Lokaler FastAPI/SQLite-MVP für Bestellungen, menschliche Freigabe, Küche, Fahrerauslieferung und Reporting. Der Telefonanruf wird derzeit **im Browser simuliert**; echte Telefonie, Spracherkennung, LLM-Dialog und Sprachausgabe sind noch nicht angebunden. **Meine weiteren öffentlichen Projekte:** [KI-Portfolio](https://github.com/klareki-lab/Train-Today-AI-Business-Suite/blob/main/PORTFOLIO.md).

Lokal lauffähiger MVP eines KI-Telefon-Bestellassistenten für ein Lieferrestaurant (Zielmarkt Deutschland). Dieser Repo-Zustand liefert:

- einen browserbasierten Betreiberteil (Konfirmierer, Küche, Fahrer, Besitzer),
- einen Anruf-Simulator als Platzhalter für einen echten Telefonie-Provider,
- CRM, Speisekarte, Rollen-/Zugriffskontrolle,
- Dashboard mit den vier FR-15-Kennzahlen,
- persistente SQLite-Datenbank,
- automatisierte End-to-End-Tests.

Vollständiger Entwurfskontext liegt unter `outputs/claude/2026-11-01-nexus-01/` (NEXUS Phase 0 & 1). Die Design-Dokumente bleiben die autoritative Quelle für Anforderungen; dieses MVP implementiert eine erste pragmatische Interpretation davon.

## Technologie-Stack

- Python 3.11+ (getestet mit 3.14)
- FastAPI + Starlette + Jinja2 (serverseitiges Rendering)
- SQLite 3 (eingebettet; keine externen Dienste)
- bcrypt für Passwort-Hashes
- pytest + httpx für Tests

Es werden **keine** externen oder kostenpflichtigen Dienste aufgerufen. Die Code-Basis läuft vollständig offline.

## Lokaler Start

```bash
# 1. Virtuelle Umgebung + Abhängigkeiten
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Server starten (DB wird automatisch angelegt und geseedet)
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 3. Im Browser öffnen
#    http://127.0.0.1:8000/login
```

Die SQLite-Datei liegt standardmäßig unter `data/mvp.sqlite`. Alternative Lage über die Umgebungsvariable `KLARE_DB_PATH` (wird auch von den Tests genutzt).

Die Sitzungs-Signatur verwendet einen automatisch erzeugten lokalen Schlüssel neben der Datenbank (`*.session-secret`, Modus 0600, nicht committen). Alternativ `KLARE_SESSION_SECRET` setzen. Nur an 127.0.0.1 binden; Demo-Passwörter niemals öffentlich bereitstellen.

## Demo-Konten

Nur für lokale Evaluation. Nicht wiederverwenden.

| Benutzer    | Passwort        | Rolle      | Startseite  |
|-------------|-----------------|------------|-------------|
| `owner`     | `owner123`      | owner      | /dashboard  |
| `confirmer` | `confirmer123`  | confirmer  | /confirmer  |
| `kitchen`   | `kitchen123`    | kitchen    | /kitchen    |
| `courier1`  | `courier123`    | courier    | /courier    |
| `courier2`  | `courier123`    | courier    | /courier    |

Seed-Daten enthalten: 10 Menü-Positionen und einen Stammkunden (Thomas Müller, +49 30 1234567).

## Sequenz einer vollständigen Bestellung

1. Als `confirmer` einloggen → **Anruf**.
2. Telefonnummer eingeben → **CRM-Lookup** (bei `+49 30 1234567` werden Daten vorbefüllt).
3. Positionen auswählen → **Bestellung an Konfirmierer senden**.
4. Zur Prüfungsansicht wechseln → Positionen oder Adresse ggf. editieren → **Bestätigen & an Küche senden**.
5. Als `kitchen` → **Fertig** klicken.
6. Als `confirmer` → **Dispatch** → Fahrer zuweisen.
7. Als `courier1` → Auftrag öffnen → **Unterwegs** → **Navigator öffnen** (externer Deep-Link) → **Zugestellt**.
8. Als `owner` → **Dashboard** zeigt den neuen Datensatz unter „Zugestellt pro Fahrer".

Repeat-Caller-Variante: der zweite Anruf von `+49 30 1234567` zeigt den Kunden sofort als Stammkunde; die Namens-Verifikation (verbal) bleibt operative Pflicht (Guard R-B aus `design/privacy.md` und ADR-V11 aus `design/voice-ai.md`).

## Rollen und Zugriff

- Owner darf alles lesen, hat Zugriff auf Dashboard, Menü-Bearbeitung und Kunden.
- Confirmer: Anruf-Simulator, Prüfung/Freigabe, Dispatch, Kunden.
- Kitchen: nur Küchen-Warteschlange; keine Kundendaten (Need-to-know).
- Courier: eigene Aufträge; Rufnummer ist standardmäßig **nicht sichtbar** und wird erst auf expliziten „Anrufen"-Klick aufgedeckt (Audit-Event in `access_log`). Reconciliation aus Reality-Check-Runde 1 (F-10).

## Automatisierte Tests

```bash
.venv/bin/python -m pytest
```

Deckt ab:

- Erstanruf-Lebenszyklus (new → confirmed → in-kitchen → ready → assigned → en_route → delivered → closed).
- Stammkunden-Lookup und CRM-Match.
- Zugriffsgrenzen (Fahrer darf keine Konfirmierer-Queue sehen; Küche sieht keine Kunden; Anonymer Zugriff blockiert).
- Rejected-Pfad verhindert Kitchen-Progression (HTTP 409).
- Persistenz über Prozess-Neustart (gleicher DB-Pfad).

Testlauf-Status: **5 passed** (Stand des letzten Commits).

## Voice-Integration — ehrliche Abgrenzung

Die Datei `app/voice/interface.py` definiert einen `VoiceProvider`-Vertrag mit `CallMeta` und `CapturedOrder` entsprechend `design/voice-ai.md §7.1`. Die aktuelle Implementierung (`app/voice/simulator.py`) ist **ausdrücklich ein Simulator** — kein SIP-Trunk, kein ASR, kein LLM, kein TTS. Sie erzeugt echte strukturierte Bestellungen im System, aber ohne Audio-Verarbeitung.

Für echte Telefonie ist eine zweite Implementierung des Interfaces notwendig:
- SIP/PSTN-Terminierung (z. B. ein Media-Server + Trunk).
- Streaming-STT auf deutsch.
- LLM-Dialog mit Function-Calling nach dem Order-Schema (§7.1).
- Streaming-TTS auf deutsch.
- Durchsetzung des Policy-Defaults `recording_stored=False`.

Verbindlicher Zusatzschritt vor Pilotbetrieb: offene Punkte aus `handoffs/gate-1.md`, Legal-Review der DE/EU-Vorgaben (`design/privacy.md`), DPIA.

Der Simulator wird in der UI explizit als solcher gekennzeichnet (`app/templates/call_simulator.html`), um die EU-AI-Act-Transparenzverpflichtung nicht zu konterkarieren.

## Projektstruktur

```
app/
  main.py                # FastAPI-App, Routen
  db.py                  # SQLite-Schema und Verbindung
  auth.py                # Login, Rollen, Zugriffs-Dependency
  orders.py              # Zustandsmaschine FR-19
  seed.py                # Idempotentes Seeding
  voice/
    interface.py         # VoiceProvider-Vertrag
    simulator.py         # Browser-Simulator-Implementierung
  templates/             # Jinja2-Templates
  static/style.css       # Styles
tests/
  conftest.py            # TestClient-Fixture mit isolierter SQLite
  test_e2e_flow.py       # Lebenszyklus, Rollen, Persistenz
data/                    # SQLite-Datei (gitignored)
outputs/                 # NEXUS Phase 0/1 Design-Pakete (unverändert)
docs/experiment/         # Experiment-Protokoll & Registry
brief/                   # Ursprüngliche Produktidee
```

## Umgesetzte Features (vs. Pflichtliste)

- [x] Browserbasierter Betreiber-Teil (Rollen owner/confirmer/kitchen/courier).
- [x] CRM der Kunden und Adressen.
- [x] Katalog Blüte und Preise (`/menu`).
- [x] Erstellung einer Bestellung über Anruf-Simulator.
- [x] Bestätigung oder Korrektur durch Menschen (Konfirmierer-Review-Screen).
- [x] Weitergabe an die Küche nach Bestätigung.
- [x] „Fertig"-Markierung durch die Küche.
- [x] Fahrer-Zuweisung (Dispatch-Screen).
- [x] Mobile Fahrer-Ansicht mit Adresse und Navigator-Start.
- [x] Lieferbestätigung mit Phone-Reveal + Audit.
- [x] Dashboard mit FR-15-Kennzahlen (zubereitet, zugestellt pro Fahrer, Summen, Tagesabschluss).
- [x] Persistenz über Prozess-Neustart (SQLite-Datei).
- [x] Echte Rollen-/Zugriffskontrolle (Session-Cookies, FastAPI-Dependencies).
- [x] Automatisierte Tests des Grundprozesses.

## Nicht umgesetzt / bewusst zurückgestellt

- Echter SIP/ASR/LLM/TTS-Stack (siehe Voice-Integration oben).
- Multi-Location / Multi-Tenant.
- Zahlungserfassung (Bestellsummen werden berechnet, aber nicht abgerechnet).
- Automatische Zuweisung an Fahrer; aktuell manuell im Dispatch.
- Offline-Queue der Fahrer-App (PWA ohne Service-Worker in v1).
- Allergen-Workflow / LMIV-Pflichten im Dialog.
- Externe Adress-Validierung / Delivery-Zone-Prüfung.
- OIDC/SSO; bcrypt-Passwörter sind lokal, kein Externer IdP.
- Observability-Stack (Logging ist stdlib, keine Metriken-Exporte).

## Sicherheits- und Datenschutz-Anker (Design → MVP)

- Rollen-basierter Zugriff mit „need-to-know"-Scoping für Küche und Fahrer (`design/privacy.md §7.2`, F-10-Reconciliation).
- `recording_stored` ist Default `False` (`ADR-P-03`, `ADR-V8`).
- Phone-Reveal auf dem Fahrer-Screen schreibt `access_log`-Eintrag (ADR-SA-5-adjacent, F-10-Reconciliation).
- Audit-Trail über `order_events` für jede Zustandsänderung.
- Session-Cookie signiert (itsdangerous via SessionMiddleware); max-age 12 h.
- Standardwarnung in `call_simulator.html`, dass es sich **nicht** um echte Telefonie handelt.

Diese Mechanismen ersetzen keine DPIA und keine Rechtsprüfung (`Needs legal review:` aus `design/privacy.md` bleibt in Kraft).

## Lizenz & Nutzungshinweise

Dieses MVP ist ein Experiment. Es darf nicht ohne vorherige Rechts-, Datenschutz- und Produktprüfung mit echten Kundendaten betrieben werden.

## Codex local acceptance

`.venv/bin/python scripts/local_acceptance.py` starts a temporary loopback-only server with a synthetic database, exercises delivery and restarts the process. Run `.venv/bin/python -m pytest -q` for negative and security regressions. Handoff: `docs/agents/CURRENT_STATE.md`.
