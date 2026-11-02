# MVP Readiness — Klare KI Restaurant Blueprint

Stand: 2026-11-02. Zweig `feat/restaurant-blueprint`, Basis-Commit `c472d3b`
(MISSION 10 Demo Release). MISSION 11 (`feat/autonomous-takeover-hardening`)
betrifft nur das Agent-Runner-Repo und ist für Blueprint nicht einzubeziehen.

## 1. Was lokal funktioniert

- Blueprint-Übersicht `/blueprint` und Demo `/blueprint/demo` für alle
  eingeloggten Rollen.
- Diagnose-Profil CRUD für `owner`:
  anlegen (`POST /blueprint/diagnose/new`), öffnen, Statuswechsel
  (`draft → review → shared`), löschen (`POST /blueprint/diagnose/{id}/delete`).
- Pro Diagnose-Bereich eine eigene Seite mit Status-Auswahl (Radio),
  Werkzeugfeld, Qualität 1–5, Automatisierungsgrad 1–5, geschätzter
  Zeitverlust und optionaler Verifizierungs-Marker; Upsert via
  `INSERT ... ON CONFLICT DO UPDATE`.
- Freitext-Redaction: Serverseitiges Entfernen von Telefonnummern (≥ 7 Ziffern),
  E-Mail- und IBAN-Mustern; getriggerte Redaktion wird in `access_log` als
  `blueprint.notes.redacted` protokolliert.
- Vorschlags-Ansicht `/blueprint/proposal/{id}` mit Katalog-Auswahl und
  Prioritätssetzung je Verbesserung.
- Druckfähiger HTML-Report `/blueprint/proposal/{id}/report` mit Print-CSS,
  Katalog-Version, Vertraulichkeits-Fußzeile und Markierung „Richtwert
  Klare KI, nicht Angebot".
- Audit-Log: alle schreibenden Blueprint-Routen schreiben in `access_log` mit
  Konvention `blueprint.<entity>.<verb>`.

## 2. Testabdeckung

- Baseline-Regression: alle **40 bestehenden Tests** bleiben grün.
- **24 neue Blueprint-Tests** (`tests/test_blueprint.py`):
  RBAC-Durchsetzung je Rolle, Profil-CRUD, Area-Upsert-Idempotenz,
  **Löschkaskade** über Findings und Selections,
  Gap-Logik (unknown ≠ Lücke, available = kein Vorschlag, missing = High),
  Vorschlags-Auswahl + Report-Rendering, Redaction, Audit-Log-Einträge,
  reine Unit-Tests für `gap.analyze`.

Gesamt: **64/64 Tests grün** auf Python 3.14 mit dem im Repo gepflegten Venv
nach Umsetzung der Reality-Check-Fixes.

Siehe `README.md` oder `Makefile` für den Testaufruf:

```
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q
```

## 3. Demonstrations-Szenario (akzeptiert)

Ausgeführt lokal, Rolle `owner` (Zugang: `owner` / `owner123`, lokale Demo-
Zugangsdaten aus `app/seed.py` — nicht produktionstauglich):

1. `/blueprint` öffnen → Übersicht und Sub-Navigation.
2. `/blueprint/demo` → Pizzeria „Bella Vita" mit Verweisen auf die
   bestehenden Modi (Call Simulator ausdrücklich als Simulator markiert).
3. `/blueprint/diagnose/new` → Profil für eine fiktive Pizzeria anlegen.
4. Für mindestens einen Bereich (z. B. `phone` als „missing") eine Antwort
   erfassen.
5. `/blueprint/proposal/{id}` → Verbesserung „KI-Telefonannahme" wird mit
   hoher Priorität vorgeschlagen; Auswahl treffen und speichern.
6. `/blueprint/proposal/{id}/report` → Druckfähiger Report in Deutsch mit
   Katalog-Version und Vertraulichkeits-Fußzeile.

Automatisiert geprüft in `test_proposal_selection_and_report`.

## 4. Was explizit **nicht** passiert ist

- **Keine Browser-Druckprüfung**: Die Print-CSS-Regeln sind implementiert,
  aber nicht visuell gegen Chrome/Safari/Firefox verifiziert. Dies ist ein
  HTTP-/HTML-Test, keine Druck-Akzeptanz.
- **Keine externen Dienste**: Keine Anbindung an POS, Telefonie,
  Lieferplattformen, E-Mail oder Buchhaltung. Alle solchen Punkte sind im
  Katalog als `verified=False` markiert und im Report entsprechend gelabelt.
- **Keine Produktionsdaten**: Alle Diagnose-Profile sind lokal in SQLite.
- **Keine Rechtsprüfung**: Datenschutz-Review liegt vor, qualifizierte
  juristische Prüfung steht aus (siehe `04-privacy-engineer.md`).
- **Keine Barrierefreiheits-Audit** (WCAG-Konformität nicht formal geprüft).

## 5. Bekannte Einschränkungen

- Status-Chips verwenden Pastellfarben, deren Kontrast gegen Text nicht
  WCAG-AA automatisiert geprüft wurde. Visuelle Prüfung empfohlen.
- Der Redactor für Telefonnummern kann theoretisch falsch-positiv bei
  zusammenhängenden Zahlensequenzen zuschlagen; der Mindestlängen-Filter
  (≥ 7 Ziffern) senkt das Risiko und ist durch
  `test_notes_short_fragment_is_not_redacted` abgesichert.
- `_home_for(owner)` leitet weiterhin auf `/dashboard`, nicht auf
  `/blueprint`. Topbar-Link führt zu Blueprint.

## 6. Nächste Schritte (falls genehmigt)

- Reality-Checker-Review einarbeiten.
- Codex-Review in `outputs/codex/` (nur wenn separate Codex-Sitzung
  autorisiert und tatsächlich verfügbar; sonst ausstehend).
- Draft-Pull-Request zur Besprechung mit Product Owner, kein Merge.
