# Draft PR — feat/blueprint-decision-engine-fix (MISSION 16)

Basis: PR #10 (`feat/blueprint-commercial-remediation`, Commit `53baebe`).
Zweck: minimale Korrektur der sieben Codex-Blocker (R1–R7) aus MISSION 15
(Verdikt FAIL). Kein Merge, keine Codex-Zweitabnahme, keine Produktbreite
Erweiterung.

## Kern-Prinzip

Ein fehlendes Katalog-Modul ist nicht dasselbe wie ein fehlender Bedarf.
Ein gut geführter manueller Prozess ist nicht dasselbe wie eine Baustelle.
Ein Freitext, der ein Thema negiert, ist nicht dasselbe wie ein genanntes
Problem. Die Engine respektiert diese drei Trennungen jetzt explizit.

## Zusammenfassung der Fixes

- **R1** `_strong_pain` entfernt `automation`-Score als Beweis für Belastung.
  Pain wird nur noch anerkannt bei messbarer Qualität (≤2), messbarem
  Zeitverlust (≥60 min/Tag) oder einem affirmierten Problem-Keyword in
  Notizen (mit Negationskontrolle). `_staff_automation` schlägt bei
  manuellem Prozess ohne nachweisbare Belastung `not_applicable` vor,
  statt zu verkaufen.
- **R2** Neue `ProblemArea`-Erkennung in `gap.py` — unabhängig vom Katalog.
  Neuer Outcome `problems_without_match` wird im Report und im Vorschlag
  mit eigenem Banner gerendert. Keine fiktive Zahlungs-Integration.
- **R3** `_review_mgmt` verlangt eine Problem-Affirmation neben einem
  Review-Keyword; „Keine Probleme mit Google-Bewertungen" oder „werden
  beantwortet" bleibt `not_applicable`.
- **R4** `_ai_phone_reception`, `_kds`, `_crm_automation` erhalten eine
  eigene `available + strong_pain`-Verzweigung mit korrekter Evidence
  („Status: vorhanden mit genannter Belastung"). Kein „Status: teilweise"
  mehr für `available`-Inputs.
- **R5** Neuer Helfer `_calibrated_confidence` setzt `high` nur, wenn das
  Finding verifiziert ist oder quantifizierbare Daten/Notizen trägt. Bare
  `status=missing` ohne Zusatzinfo → `medium`.
- **R6** Legacy-Migration korrigiert: `priority_source` default `'auto'`
  bei neuer Spalte; idempotentes Backfill `UPDATE … SET priority_source=
  'auto' WHERE selected=0`. Zusätzlich filtern `proposal_view` und
  `proposal_report` manuelle Overrides nach `selected=1`.
- **R7** `app/main.py` Dispatch-SQL liest jetzt `'status.failed_delivery'`
  (statt des stillen `state.`-Mismatches). Grund + Zeitstempel + HTML-
  Escaping durch Regression gedeckt.

## Pflicht-Szenarien A–H

Vollständige Matrix in `docs/blueprint/MISSION_15_CLOSURE_MATRIX.md`.

| Szenario | Zustand | Erwartung |
|---|---|---|
| A | Manuell + reale Verluste | `has_findings` mit Phone/KDS/Dispatch |
| B | POS + Lieferando, keine eigenen Fahrer | `delivery_mgmt` → `not_applicable` |
| C | Alles automatisiert | `no_need`, keine CTA |
| D | Gesunder manueller Prozess (loss=0) | kein `required` |
| E | Zahlung fehlt, kein Katalog-Modul | `problems_without_match` |
| F | Widersprüchlich / unvollständig | Confidence nicht `high`; kein `required` ohne Signal |
| G | Legacy-Profil mit MISSION-12-Schema | Neue Engine-high überlebt alte medium-Overrides |
| H | Failed Delivery mit Grund-Text | Grund + Zeitstempel sichtbar, HTML escaped, RBAC |

## Tests

- 88 bestehende Tests bleiben grün (davon 1 explizit umgezogen: alte
  Erwartung `confidence='high'` für bare missing war der von Codex als R5
  gemeldete Fehler; neuer Test deckt verified vs. unverified).
- 26 neue Tests in `tests/test_mission16.py` — R1–R7, Szenarien A–H,
  Evidence-Integrität, neues Outcome-Rendering.

Gesamt: **114/114 passed**, Python 3.14, Projekt-Venv.

## Bewusste Grenzen

- Keine neuen Produktmodule (Zahlung, LMIV usw.).
- Keine Codex-Zweitabnahme — vor jedem Merge Pflicht, nur in separater
  autorisierter Codex-Sitzung.
- Keine Browser-/Druck-Verifikation (Werkzeug-Grenze; Codex-FAIL-Report
  markiert Print als NOT VERIFIED).
- Kein `force-push`, kein Merge, keine Änderungen an Agent-Runner.
- Kein Auto-Port von `feat/autonomous-takeover-hardening`.

## Prüfpunkte für Reviewer

- `grep -n "state\.failed_delivery" app/main.py` → leer.
- Lint: `_strong_pain` enthält keinen Vergleich mit `automation`.
- `gap.GapResult.outcome` kennt `problems_without_match`.
- Datenbank-Backfill ist idempotent und ändert bestehende selected=1-Zeilen
  nicht.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
