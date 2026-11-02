# Draft PR — feat/restaurant-blueprint

Dieses Dokument ist der Entwurf für die Pull-Request-Beschreibung. Der Branch
wird **nicht** automatisch gemergt. Keine Push-Operation auf `main` erfolgt
ohne ausdrückliche Freigabe.

## Zusammenfassung

Fügt den Modus **„Klare KI Restaurant Blueprint"** als Erweiterung der
bestehenden FastAPI-App hinzu. Blueprint ersetzt keine bestehenden Module,
sondern:

- **DEMO** zeigt das Referenz-Restaurant mit Verweis auf die bestehenden
  Oberflächen (Call Simulator, Konfirmierer, Küche, Dispatch, Fahrer,
  Dashboard, Kunden, Menü).
- **DIAGNOSE** erfasst 12 Bereiche eines befragten Betriebs mit 5 Status
  (`available/partial/manual/missing/unknown`) sowie Qualität,
  Automatisierungsgrad und optional geschätztem Zeitverlust pro Tag.
- **PROPOSAL** erzeugt eine druckbare Diskussionsgrundlage mit ausgewählten
  Verbesserungen aus einem Katalog von 9 Modulen (KI-Telefonannahme,
  Vereinheitlichte Bestellannahme, KDS, Dispatch, CRM-Automatisierung,
  Betreiber-Analytik, Workflow-Automatisierung, Bewertungsmanagement,
  Automatisierung manueller Prozesse).

Alle Preis- und Zeitangaben sind als unverbindliche Richtwerte markiert.

## Was ändert sich NICHT

- Keine bestehende Route, Vorlage, Rolle oder Datenbanktabelle wird
  verändert; Blueprint fügt neue Tabellen idempotent hinzu
  (`CREATE IF NOT EXISTS`).
- Keine Produktionsdaten, keine externen APIs, keine bezahlten Dienste.
- Call Simulator bleibt als Simulator markiert, es findet keine echte
  Spracherkennung statt.
- Agent-Runner-Konfiguration bleibt unangetastet.

## Agency-Agents-Konsultation

Vor der Umsetzung wurden folgende Spezialisten (`.claude/agents/`) als
read-only Agenten aufgerufen und ihre Rückmeldungen in die Architektur
eingearbeitet:

- product-manager
- ux-architect
- software-architect
- privacy-engineer
- reality-checker (am Ende des Vorgangs)

Siehe `docs/blueprint/AGENTS_REPORT.md` für Zeitpunkte und
`outputs/claude/2026-11-02-blueprint/` für die Zusammenfassungen.

## Dokumente

- `docs/blueprint/BLUEPRINT_ARCHITECTURE.md` — finale Architektur.
- `docs/blueprint/INTEGRATIONS.md` — Status aller genannten Integrationen
  (alle **unbestätigt**).
- `docs/blueprint/MVP_READINESS.md` — was lokal funktioniert, was explizit
  nicht geprüft wurde.
- `docs/blueprint/adr/ADR-01..03` — Katalog als Code, APIRouter, Katalog-
  Version pro Profil.
- `docs/blueprint/AGENTS_REPORT.md` — Agenten-Einsatzprotokoll.

## Tests

- Bestehende 40 Tests bleiben grün (`tests/test_e2e_flow.py`,
  `tests/test_demo_release.py`, `tests/test_hardening.py`).
- 24 neue Tests in `tests/test_blueprint.py`:
  RBAC, Profil-CRUD, Area-Upsert-Idempotenz, Löschkaskade über Findings
  und Selections, Gap-Logik, Vorschlags-Auswahl, Report-Pflichtinhalte,
  Freitext-Redaktion, Audit-Log-Einträge, reine Unit-Tests der Gap-Analyse.

Gesamt: **64/64 Tests grün** nach Reality-Check-Fixes.

## Nicht getan (bewusst)

- Visuelle Browser-Druckprüfung des Reports (kein automatisierter Zugang).
- Qualifizierte DSGVO-Rechtsprüfung (dokumentiert als ausstehend).
- Externe Integrationen (bewusst nicht umgesetzt; alle `verified=False`).
- Codex-Zweitprüfung in `outputs/codex/` (nur wenn separate autorisierte
  Codex-Sitzung tatsächlich verfügbar).

## MISSION 11

MISSION 11 (`feat/autonomous-takeover-hardening`, `8471c4d`) betrifft das
Agent-Runner-Repo, nicht die Restaurant-App. Basis von Blueprint ist daher
`c472d3b` (PR #8 / MISSION 10 Demo Release); eine spätere Integration ist
nicht erforderlich.

## Prüfpunkte für den Reviewer

- Alle Blueprint-Routen hinter `require_strict("owner")` außer Overview + Demo.
- Keine Katalog-Beschreibung enthält unbelegte Minuten-/Umsatzzusagen.
- Report-Fußzeile und Vertraulichkeitshinweis gerendert.
- Redaction greift auf Telefon-/E-Mail-/IBAN-Mustern, nicht auf kurzen
  Mengenangaben.
- SQLite-Schema wird nur additiv erweitert.
