# MISSION 14 — Remediation Plan (Entwurf)

Status: *Entwurf — wird von Product/UX/Reality-Spezialisten geprüft, bevor
Codex die Umsetzung erneut unabhängig abnimmt.*

Grundlage: Codex MISSION 13 QA_REPORT.md, FUNCTION_MATRIX.md, FIX_PLAN.md
und MISSION 12B REVIEW.md. Verdikt: FAIL für kommerzielle Nutzung des
Blueprint. Zehn Defects (D01–D10) sind nachgewiesen.

## Produktprinzip (unverrückbar)

Blueprint liefert *objektive Diagnose*. Wenn ein Restaurant keinen
Verbesserungsbedarf hat, muss der Bericht genau das zeigen — nicht ein
auf eine Klare-KI-Hub-Verkaufschance umschreiben.

## Priorisierte Fixes

### 1. D03 + D10 · Katalog entkoppelt von eigenem MVP, Applicability-Gate

Katalog-Datenstruktur bekommt neue Felder:

- `applicability(finding) -> Applicability`: liefert einen von
  `required` / `conditional` / `not_applicable` / `insufficient_data`.
  Prüft neben Status auch Quality, Automation, Current-Tool und
  type-spezifische Signale (own delivery vs platform, phone active vs
  missing).
- `evidence(finding) -> list[Evidence]`: nachvollziehbare Treiber
  („Status: manual", „Qualität 1 von 5", „aktuell: Zettelwirtschaft",
  „Lieferando aktiv, keine eigenen Fahrer").
- `preserved_systems` zeigt den **tatsächlichen Werkzeug-Namen** aus der
  Diagnose (`current_tool`), nicht die Klare-KI-MVP-Oberflächen.
  Platzhalter wird im Report mit „aktuell genutzt: {current_tool}" ersetzt.
- Modulbeschreibungen gewichten „Konfiguration/Modul des Bestandssystems"
  vor „Eigene Erweiterung".

### 2. D06 · Ergebnis „kein Implementierungsbedarf"

Wenn das Engine 0 Suggestions produziert und ≥ 10 der 12 Bereiche
beantwortet sind, zeigt der Report:

> Aktuell kein zusätzlicher Implementierungsbedarf festgestellt.

und ersetzt die Blocks „Nächste Schritte: Audit mit Zugängen + Angebot".
Stattdessen: optionale Hinweise zu Verifizierungs-Lücken (`available` +
`verified=0`) und zu `unknown`-Bereichen.

Nicht derselbe Zustand wie „noch keine Antworten vorhanden".

### 3. D04 + D07 · Evidence-driven Scoring statt reine Status-Rangliste

- `Suggestion` trägt `evidence: list[Evidence]` und `confidence: low|medium|high`.
- Prioritäts-Logik: `manual` + `quality <= 2` + `time_loss > 60` → high.
  `manual` ohne weitere Evidenz → medium. `missing` + `applicability
  == required` → high. Sonst low.
- Priorität wird im Report als „Vorschlag, keine Dringlichkeits­bewertung"
  gekennzeichnet.
- Report-Block pro Vorschlag listet Driver + Beobachtung +
  Werkzeug + Hinweise des Betreibers. Freitexte wandern durch den
  bestehenden Redactor.

### 4. D05 · Priorität nur bei expliziter Nutzerauswahl persistieren

- `priority_source TEXT NOT NULL DEFAULT 'auto'` ergänzen; manuelle
  Override bekommt `'manual'`.
- Auswahl-Formular schreibt **nur** die tatsächlich ausgewählten Codes
  (ehemals: alle Katalog-Codes mit `medium`). Priorität automatisch
  berechnet aus Engine, nur bei explizitem Override gespeichert.
- Vorhandene Rows ohne Override bleiben automatisch gesteuert; neue
  Vorschläge erhalten ihre korrekte Engine-Priorität.

### 5. D01 · Profil-Reiter bearbeitbar

- `GET /blueprint/diagnose/{id}/edit`, `POST /blueprint/diagnose/{id}/edit`
  mit RBAC + Audit (`blueprint.profile.update`), Zeichen-Limits identisch
  zu `/new`, kein Löschen der Findings.
- Link vom Profil-Overview.

### 6. D02 · Zero vs Blank Round-Trip

- Jinja: `value="{{ finding.time_loss_min_per_day if finding.time_loss_min_per_day is not none else '' }}"` statt `… or ''`.
- Analog für `quality`, `automation`.
- Server: `_int_or_none` behandelt leeres → `None`, `"0"` → `0`.

### 7. D08 · Failed-delivery Recovery

- `/dispatch` zeigt zusätzlich den Block „Fehlgeschlagene Zustellungen".
- Routen:
  - `POST /dispatch/{id}/retry` → requires `status == 'failed_delivery'`,
    weist einem neuen Fahrer zu, Transition `failed_delivery → assigned`
    (neuer order_event mit `detail=retry_by=…`).
  - `POST /dispatch/{id}/cancel` → requires `status == 'failed_delivery'`,
    transition zu `cancelled` mit begründeter `reject_reason`.
- RBAC: `owner` oder `confirmer`.
- Nicht-passende Status → 409.
- Audit-Log plus Order-Event-Log.
- Keine Behauptung über Rückerstattung oder Platform-Sync.

### 8. D09 · Mobile Responsive für Blueprint-Tabellen

- Blueprint-spezifische Media-Query < 640 px:
  - Diagnose-Liste und Profil-Bereiche: `display:block` als „Karten", jede
    Zelle mit `data-label` oder `::before`-Label.
  - Proposal-Tabelle: horizontaler Scroll-Container
    (`overflow-x:auto; -webkit-overflow-scrolling: touch`).
  - Report-Tabellen: schmalerer Font + Scroll-Fallback.
- Keine Veränderung an bestehenden MVP-Tabellen.

### 9. Dokumentations-Korrekturen

- `BLUEPRINT_ARCHITECTURE.md`, `MVP_READINESS.md`, Draft-PR: Zeile zur
  MISSION 11 richtigstellen.
- Katalog-Text zur „Vereinheitlichten Bestellannahme": aus
  „Doppelerfassung entfällt" wird „Doppelerfassung kann je nach Vertrag
  und Marktplatz-Freigabe reduziert werden".
- Lieferando-Hinweis: Risikoabschnitt im Report für Katalog-Modul mit
  Lieferplattformen-Scope (Just-Eat-Takeaway-Bridge Cancellation Gap).
- Newo/TCO-Herkunft: Katalog-Richtwerte als „Interne Schätzung Klare KI,
  nicht Lieferanten-Quote; keine Measured ROI".

## Nicht Teil dieses PR

- Tenant-Isolation (bewusste interne Entscheidung).
- Reale Browser-Druckprüfung (Tool-Limitation).
- Reale Vendor-Integrationen.
- Codex-Zweitprüfung (nur bei autorisierter separater Sitzung durch PO).

## Tests

- 64 bestehende Blueprint/MVP-Tests bleiben grün.
- Neue Tests:
  - `test_commercial_scenarios.py`: A/B/C komplette Flows.
  - `test_blueprint_edit_zero_cascade.py`: D01/D02/D05.
  - `test_failed_delivery_recovery.py`: D08 inklusive wrong-state und
    foreign-role Negativfälle.
  - `test_blueprint_mobile.py`: HTML-Scope (Media-Query vorhanden, Marker
    enthalten; visuelle Prüfung weiterhin als Limitation dokumentiert).
- Reality-Checker Zweitlauf nach Umsetzung.
