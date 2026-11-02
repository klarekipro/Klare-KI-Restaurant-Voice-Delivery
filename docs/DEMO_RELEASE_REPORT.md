# Demo-Release Report — MISSION 10

Branch: `feat/restaurant-demo-release` (dediziertes Worktree). Basiert auf
Commit `8471c4d` (PR #5).

## 1. Umfang der Änderungen

| Bereich                                   | Änderung                                                                                 |
|-------------------------------------------|------------------------------------------------------------------------------------------|
| Status-Darstellung                        | 11 Status-Codes übersetzt; farbcodierte Badges (`.status-badge--*`) + Icon-Präfix.       |
| Fehlerseiten                              | FastAPI-Handler für 400/401/403/404/409 → DE Error-Template (`app/templates/error.html`).|
| Fehlermeldungen                           | Alle `HTTPException(detail=…)` auf Deutsch (Formular, Idempotenz, Rollen, Status).       |
| 401-Verhalten                             | Nicht-angemeldete Zugriffe → 303 Redirect `/login` statt rohes 401.                      |
| Idempotenz (Küche)                        | `/kitchen/{id}/ready` und `/kitchen/{id}/start` sind idempotent (kein 409 bei Doppelklick).|
| Idempotenz (Fahrer)                       | `/courier/{id}/start`, `/courier/{id}/delivered` idempotent.                             |
| Flash-Banner                              | Erfolgs-Flash nach POST-Redirect via `?flash=…` + base.html Render.                      |
| Dashboard                                 | Interne Design-Doc-Verweise entfernt; neuer Block **Küchenleistung**                     |
| Dashboard SQL                             | `failed_delivery` aus `gross_active` entfernt; inaktive Fahrer gefiltert.                |
| Audit-Trail                               | Änderungen an Stammkundendaten über Voice-Submit landen in `access_log`.                 |
| Mobile CSS                                | Safe-Area, größere Touch-Targets (≥64 px), bessere Statusbadge-Lesbarkeit.               |
| Kitchen-UI                                | Mindesthöhe pro Karte, 56–68 px Buttons, farbige Status direkt sichtbar.                 |
| Tests                                     | +11 neue Regressionstests (`tests/test_demo_release.py`), bestehende Tests angepasst.     |

Insgesamt: 2 neue Dateien, 10 geänderte Dateien, +627/-108 Zeilen (ca.).

## 2. Testergebnisse

```
.venv/bin/python -m pytest
→ 40 passed, 1 warning

PYTHONPATH=. .venv/bin/python scripts/smoke_e2e.py
→ 28/28 steps passed
```

Smoke-Skript deckt die 12 Pflichtflows + Fehler- und Persistenzpfade ab:
AI-Anruf, CRM-Lookup, Erstkunde anlegen, Konfirmierer-Review mit Edit/Add,
Approval, Küche start/fertig, Dispatch-Zuweisung, mobile Fahrer-Ansicht,
Google-Maps-Link, Lieferabschluss, Dashboard-Umsätze, Report pro Fahrer,
Idempotency-Replay/Conflict, Persistenz nach App-Neustart.

Live-HTTP-Smoke (Uvicorn auf 127.0.0.1:8777) bestätigte zusätzlich:
Login, Dashboard mit Küchenleistung-Block, Anruf-Simulator, Status-Badge
`status-badge--new` / „Neu – zu prüfen" / `status-badge--confirmed` / „Bestätigt"
in realen HTML-Antworten.

## 3. Tatsächlich eingesetzte Agency-Subagenten

| Agent                     | Zweck                                                                                   | Status      |
|---------------------------|------------------------------------------------------------------------------------------|-------------|
| software-architect        | Priorisierte Defekt-Liste (30 Punkte) über Routen, Zustandsmaschine, SQL, Error-Handling.| completed   |
| ux-architect              | DE-Copy-Sheet, Status-Farbsystem, Rollen-spezifische Layoutregeln, Mobile-Spec, Fehler-Stil.| completed   |
| reality-checker           | Unabhängige Prüfung des finalen Pakets gegen Mission-Kriterien (18 Findings).            | completed   |

### Reality-Check-Ergebnis

Der unabhängige reality-checker lieferte 18 Findings mit Verdikt
`fixes-needed-before-demo`. Die MAJORs (1, 2, 3, 6) und die wichtigsten MINORs
(4, 5, 7, 8, 9/10, 15) wurden im gleichen Lauf implementiert und mit
Regressionstests abgedeckt:

- Rolle in Navigation jetzt deutsch (`Inhaber:in` statt `owner`).
- `report_window(7)` dokumentiert; Spanne ist korrekt 7 Tage inkl. heute
  (reality-checker-Finding war Fehlalarm; Formel verifiziert).
- `customers_edit`: Pflichtfeld- und PLZ-Validierung analog Voice-Submit.
- `confirmer_reject`: Non-empty Grund erzwungen.
- `courier_delivery`-Template: Name-None-Guard eingezogen.
- Google-Maps-Deep-Link erhält `, Deutschland`.
- `courier_failed`: Transaktional, Non-empty-Grund-Prüfung, Flash-Banner.
- `avg_ticket`: em-dash statt „0,00 €", wenn keine Lieferung vorlag.
- DE-Zeitstempel-Filter (`datetime_de`, `time_de`) für Queue/Kitchen/Fahrer/Review.
- Login-Hint zeigt Demo-Zugänge direkt im UI.

MINORs 11–14, 16–18 wurden bewusst nicht adressiert (geringes Demo-Risiko).

Nach den Fixes: 40/40 Pytest + 28/28 E2E Smoke zu grün. Nicht erneut durch
reality-checker verifiziert (ein weiterer Durchlauf würde den Zyklus
verlängern; alle MAJORs sind durch Regressionstests gedeckt).

Alle drei Subagenten sind read-only; sämtliche Code-Änderungen wurden vom
Koordinator (Engineering Lead) ausgeführt und durch Tests + Live-Smoke verifiziert.

## 4. Verbleibende Grenzen und bewusste Verzichte

- **Kein echter Browser-Test**: Der Koordinator hat kein interaktives Browser-Tool.
  Verifikation erfolgte über FastAPI TestClient (TypeScript-Deep-Rendering) und
  `curl` gegen laufendes Uvicorn. Visuelle Validierung in echtem Chrome/Safari
  (Desktop und 360-px-Mobile) steht aus und sollte vor Live-Demo manuell erfolgen.
- **Keine echte Telefonie**: Simulator-only. SIP/ASR/LLM/TTS nicht angeschlossen.
- **Keine Zahlungsabwicklung**.
- **Keine automatische Fahrerzuweisung**, keine Routing-Optimierung.
- **Observability**: nur stdlib-Logging, keine Metriken-Exports.
- **CSRF**: weiterhin über Origin + Sec-Fetch-Site, kein expliziter CSRF-Token.
- **Session-Fixation**: `request.session.clear()` + neue UID ohne harte
  Session-ID-Rotation; akzeptabel für lokale Demo.
- **Datum/Zeit**: SQLite `datetime('now')` liefert UTC, Dashboard rechnet
  nach Europe/Berlin; funktioniert, aber kein konsistenter TZ-Helper.
- **Google-Maps-Link**: nutzt Deep-Link `maps/dir/?api=1&destination=…` ohne
  Länderangabe; funktioniert für DE, kann bei exotischen Adressen Mehrdeutigkeit
  erzeugen.

## 5. Was NICHT geändert wurde (laut Mission-Regel)

- `tools/agent-runner/*` (bleibt für Codex MISSION 09).
- LaunchAgent-, Planer- oder SQLite-Zustand des Kommandanten.
- Andere Git-Worktrees.

## 6. Nächster Schritt

- Manuelle Browser-Validierung auf Desktop (Chrome, Firefox) und Mobile
  (iOS Safari / Android Chrome, 360–390 px) durch Product Owner.
- Nach Freigabe: Draft-PR öffnen (nicht automatisch gemerged).
