# Draft PR — feat/blueprint-commercial-remediation (MISSION 14)

Basis: PR #9 (`feat/restaurant-blueprint`, Commit `53d04a5`).
Zweck: Umsetzung der Codex-Abnahme-Beanstandungen aus MISSION 13
(QA_REPORT.md, FIX_PLAN.md) — Blueprint wird vom Katalog-Verkaufsinstrument zu
einer objektiven Diagnoseplattform umgebaut.

Kein Merge ohne erneute unabhängige Codex-Zweitprüfung.

## Produkt-Prinzip (unverrückbar)

Wenn ein Restaurant keinen Verbesserungsbedarf hat, muss Blueprint das
*ehrlich* zeigen. Der Report darf keinen kostenpflichtigen Audit und kein
Pflicht-Angebot vorschlagen, wenn das Engine keinen Treiber findet.

## Was sich ändert

### Objektives Recommendation Engine
- Neue Datei `app/blueprint/applicability.py` — Regeln je Verbesserungs-
  Modul (`required / conditional / not_applicable / insufficient_data`).
- `app/blueprint/gap.py` komplett neu: evidenzbasiert, mit
  `Suggestion.verdict`, `reason`, `evidence`, `confidence` statt reiner
  Status-Rangliste.
- `GapResult.outcome ∈ {no_need, insufficient, has_findings}` steuert den
  Report.

### Katalog entkoppelt vom MVP
- `app/blueprint/catalog.py`: `preserved_systems` und `possible_tools` zeigen
  jetzt reale Bestandssysteme des Restaurants, keine MVP-Pfade wie
  `/kitchen` oder `/customers`. Reihenfolge: Bestandssystem → Markt →
  Eigenbau. Formulierungen „Doppelerfassung entfällt" ersetzt durch
  bedingte Variante inklusive expliziter Lieferando-Cancellation-Lücke.
- Neue Felder `primary_area`, `requires_own_delivery`,
  `requires_own_phone_channel`, `requires_direct_online_channel`.
- `CATALOG_VERSION` auf `2026-11-02.r2` angehoben.

### Report-Ausgänge
- `outcome=no_need`: eigener Banner „Aktuell kein zusätzlicher
  Implementierungsbedarf festgestellt" mit expliziter Negativ-Zusage „weder
  kostenpflichtiges Audit noch verbindliches Angebot".
- `outcome=insufficient`: Banner „Diagnose unvollständig — nicht
  entscheidungsreif" bei fehlender Antwort in einem Kernbereich (POS,
  Zahlung, Telefon, Küche).
- Jede Empfehlung trägt sichtbare Evidenz (Treiber + Beobachtung + Datenlage).

### Fixes aus FIX_PLAN
- D01: `GET`/`POST /blueprint/diagnose/{id}/edit` + Template.
- D02: Zahlen-Inputs korrekt `is not none`-geprüft; Hilfetext „0 bedeutet
  keine Zeitverluste; leer bedeutet nicht bekannt".
- D05: Schema-Erweiterung `priority_source`; `proposal_select` persistiert
  nur noch angeklickte Codes mit `priority_source='manual'`. Engine-
  Priorität bleibt sichtbar für ungeklickte Vorschläge.
- D08: Dispatch zeigt Block „Fehlgeschlagene Zustellungen"; neue Routen
  `/dispatch/{id}/retry`, `/dispatch/{id}/cancel_failed` mit State-Guard,
  Pflicht-Grund (≥ 3 Zeichen), Redactor für PII im Grund.
- D09: Blueprint-Tabellen `class="bp-stack"` + `data-label` → mobile
  Karten-Stapel < 640 px. Report mit `.scroll-table-wrapper`. Global
  `:focus-visible`-Outline.

### Dokumentation
- `MISSION_13_CLOSURE_MATRIX.md` listet pro Codex-Defekt den konkreten Fix
  und Test.
- `BLUEPRINT_ARCHITECTURE.md` und `MVP_READINESS.md` korrigieren die
  falsche „MISSION 11 = nur Runner-Infra"-Aussage.
- `REMEDIATION_PLAN.md` dokumentiert den Entwurf, bevor Spezialisten ihn
  bewertet haben.

## Agency-Agents (tatsächlich aufgerufen)

| Rolle | Agent-ID | Scope |
|---|---|---|
| product-manager | a0ec5938e82d3073e | Katalog-Umschreibung, No-Audit-Guardrail, Schwelle „kein Bedarf" |
| ux-architect | a7d7dd1126583f18b | Mobile Strategie je Tabelle, Edit-Flow, Failed-Delivery-UI, A11y |
| reality-checker | a2316b89d0730b47b | Unabhängige Zweitprüfung der Umsetzung |

Zusammenfassungen unter `outputs/claude/2026-11-02-remediation/`.

## Tests

- 64 Tests aus MISSION 12/13 bleiben grün.
- 24 neue Tests in `tests/test_remediation.py` (D01–D10 Regression + A/B/C-Szenarien + Katalog-Lint).
- Gesamt: **88 Tests grün**.

## Nicht in diesem PR

- Codex-Zweitprüfung in `outputs/codex/mission-14/` — Pflicht vor jedem
  Merge, aber nur über separate autorisierte Codex-Sitzung.
- Visuelle Browser-Druckprüfung (Werkzeug-Grenze).
- Multi-Tenant-Isolation (bewusste interne Entscheidung).
- Automatischer Port von `feat/autonomous-takeover-hardening`.

## MISSION 13 Codex-Vorgaben

Volle Matrix: `docs/blueprint/MISSION_13_CLOSURE_MATRIX.md`. Jeder Defekt
D01…D10 ist mit konkretem Code- und Test-Pfad belegt.
