# Closure-Matrix — MISSION 13 Defekte → Remediation (MISSION 14)

Grundlage: Codex-Abnahme am Commit `53d04a5` (QA_REPORT.md, FIX_PLAN.md).

Diese Matrix dokumentiert pro Defekt, wo im Code / Template / Test die
Korrektur steht und mit welchem Test der Fix lokal belegt wird. Keine
Behauptung einer unabhängigen Zweitabnahme — diese bleibt für Codex
reserviert.

| Codex-ID | Fix (Code / Template) | Regressionstest |
|---|---|---|
| **D01 — Keine Edit-Route für Profil-Stammdaten** | Neue Routen `GET`/`POST /blueprint/diagnose/{id}/edit` in `app/blueprint/routes.py` (`diagnose_edit_form`, `diagnose_edit_submit`); neues Template `diagnose_edit.html`; Edit-Button im Profil-Overview; Audit-Log `blueprint.profile.update detail=basics`. | `test_d01_edit_route_updates_profile`, `test_d01_edit_requires_owner`, `test_d01_edit_rejects_empty_name` in `tests/test_remediation.py` |
| **D02 — Numerische Null wird zu leer / NULL** | `diagnose_area.html`: alle drei Zahlen-Inputs nutzen `{% if finding.X is not none %}{{ finding.X }}{% endif %}` statt `… or ''`. Server behandelt `""` → `None`, `"0"` → `0` bereits korrekt in `_int_or_none`. Hilfetext „0 = keine Zeitverluste; leer = unbekannt" ergänzt. | `test_d02_zero_time_loss_survives_round_trip`, `test_d02_blank_time_loss_remains_null`, `test_d02_zero_quality_rejected_as_out_of_range` |
| **D03 — Automatik verkauft Katalog unabhängig vom tatsächlichen Bedarf** | Neue Datei `app/blueprint/applicability.py` mit Regeln je Verbesserungsmodul (`required / conditional / not_applicable / insufficient_data`). `gap.py` nutzt diese Regeln; Vorschläge entstehen nur noch bei konkretem Treiber. Katalog-Beschreibungen in `catalog.py` auf Reihenfolge „Bestandssystem → Markt → Eigenbau" umformuliert; „Doppelerfassung entfällt" ersetzt durch bedingte Formulierung. | `test_scenario_A_manual_restaurant_gets_concrete_recommendations`, `test_scenario_B_platform_only_delivery_hides_dispatch_module`, `test_scenario_C_fully_automated_restaurant_shows_no_need`, `test_unknown_phone_does_not_fire_phone_module` |
| **D04 — Scoring nur status-basiert, keine Evidenz** | `Suggestion` trägt jetzt `verdict`, `reason`, `evidence`, `confidence`. Prioritätsvorschlag kommt aus `_engine_priority(verdict, confidence)` und wird im UI/Report klar als „Vorschlag — keine Dringlichkeitsbewertung" ausgewiesen. Evidenz-Liste (`area → Beobachtung`) im Report sichtbar. | `test_gap_unit_missing_phone_proposes_high` (verdict + confidence), Observations-Zitate in `test_scenario_A_…` („geschätzter Zeitverlust 180 min/Tag") |
| **D05 — Selection-Save erzeugt stille Medium-Overrides für alle Katalog-Codes** | `proposal_select` in `routes.py`: `DELETE` + `INSERT` ausschließlich für tatsächlich angekreuzte Codes mit `priority_source='manual'`. Schema-Erweiterung `priority_source` (migrationsfähig in `_ensure_selections_priority_source`). Proposal-/Report-Context nutzt `_engine_priority` als Fallback; manuelle Override wird separat als Chip „manuell" sichtbar. | `test_d05_priority_only_persists_for_ticked_boxes`, `test_d05_new_suggestion_keeps_engine_priority` |
| **D06 — Report fordert Audit und Angebot auch wenn 0 Vorschläge** | `gap.outcome` liefert `no_need` / `insufficient` / `has_findings`. Report rendert für `no_need` einen eigenen Banner mit „Aktuell kein zusätzlicher Implementierungsbedarf festgestellt" und ersetzt „Nächste Schritte" durch optionalen Hinweis. Kernbereiche (POS, Zahlung, Telefon, Küche) müssen beantwortet sein. | `test_scenario_C_fully_automated_restaurant_shows_no_need`, `test_scenario_C_core_unknown_blocks_no_need` |
| **D07 — Report ohne Evidenz, warum Modul für diesen Betrieb** | Report rendert pro Vorschlag `reason`, `evidence`, `confidence`, Observations. Freitext läuft weiterhin durch den bestehenden Redactor. | implizit in `test_scenario_A_…` (Observation-Zitat); `test_d10_report_uses_current_tool_not_mvp` (preserved-system-Zeile) |
| **D08 — Failed-Delivery nicht wiederherstellbar** | `/dispatch` zeigt neuen Block „Fehlgeschlagene Zustellungen". Neue Routen `POST /dispatch/{id}/retry` und `POST /dispatch/{id}/cancel_failed` in `app/main.py` mit RBAC (`owner`/`confirmer`), State-Guard (409 bei falschem Status), Pflicht-Grund ≥ 3 Zeichen und Redactor-Pass. `base.html` ergänzt Flash-Nachrichten `retried`, `cancelled`. | `test_d08_dispatch_shows_failed_queue`, `test_d08_retry_reassigns_order`, `test_d08_retry_rejects_wrong_status`, `test_d08_cancel_requires_reason_and_redacts_pii`, `test_d08_courier_cannot_cancel_from_dispatch` |
| **D09 — Mobile Overflow 390 px** | Blueprint-Tabellen tragen `class="bp-stack"` mit `data-label`; neue Media-Query in `style.css` verwandelt Tabellen in Karten-Stapel. Report nutzt `.scroll-table-wrapper` als Scroll-Container. Globaler `:focus-visible`-Outline ergänzt. | `test_d09_blueprint_tables_marked_for_stack`, `test_d09_report_table_has_scroll_wrapper`. Visuelle Browser-Prüfung weiterhin ausserhalb automatisierter Testbarkeit — als bekannte Limitation dokumentiert. |
| **D10 — Katalog unterstellt eigene Klare-KI-Oberflächen als Bestand** | `catalog.py` komplett umgeschrieben: `preserved_systems` und `possible_tools` beschreiben allgemeine Bestandssysteme, keine MVP-Pfade. `gap.preserved_system_label` ersetzt den Platzhalter zur Laufzeit durch den eingegebenen `current_tool`; Fallback-Texte nach Produkt-Review. Neue Felder `primary_area`, `requires_own_delivery`, `requires_own_phone_channel`, `requires_direct_online_channel`. `CATALOG_VERSION` auf `2026-11-02.r2` gehoben. | `test_d10_report_uses_current_tool_not_mvp`, `test_d10_report_fallback_text_when_tool_empty`, `test_catalog_text_free_of_mvp_paths`, `test_catalog_text_free_of_roi_promises` |

## Zusatz-Themen aus MISSION 13 (ausserhalb der D-Liste)

- **MISSION 11 Dokumentations-Richtigstellung**: Codex merkte an, dass die Behauptung „MISSION 11 betrifft nur Runner-Infra" falsch war — der gespeicherte Patch enthielt App-Änderungen (`app/main.py`, mehrere Templates). Korrektur in `docs/blueprint/BLUEPRINT_ARCHITECTURE.md` und `docs/blueprint/MVP_READINESS.md`. Zusätzlich: der tatsächliche MISSION-11-Patch (`feat/autonomous-takeover-hardening`) wurde geprüft und *nicht* automatisch übernommen, weil er auf einem anderen Branch-Zweig lag und D08 nicht direkt löst. D08 wurde stattdessen frisch implementiert.
- **Lieferando-Cancellation-Risiko**: Im Katalog-Modul `unified_order_intake` steht nun ausdrücklich „einige Kanäle liefern Stornierungen nicht automatisch zurück" sowie „Zuständigkeit für manuelle Nacharbeit nicht übertragener Statuswechsel" als Pflicht-Verifikation.
- **Newo/TCO**: Als `Newo (potenzieller Dritter)` mit Zusatz „Markt-Kandidat, keine E2E-Verifikation vorhanden"; Budget-Spannen tragen weiterhin Label „Richtwert Klare KI, kein Angebot. Keine Lieferanten-Quote."
- **n8n**: nicht Teil des aktuellen Katalogs; `workflow_automation.possible_tools` nennt `n8n-Flows` nur mit expliziter Bedingung „bei dokumentiertem Prozess und bestimmter Zielsystem-Schnittstelle".

## Nicht gemacht (bewusst)

- **Browser-Druck-Preview**: weiterhin ausserhalb der verfügbaren Werkzeuge; wird explizit als Limitation ausgewiesen.
- **Multi-Tenant-Isolation**: Produktmodell bleibt internes Vertriebswerkzeug mit gemeinsamer Owner-Sicht.
- **Neue Status-Codes** (z. B. `not_applicable`) für Diagnose-Antworten: Produkt-Review empfahl das; wurde zugunsten der aktuell schon vorhandenen Signale (`couriers=missing` + `delivery_platforms` aktiv) für diese Iteration zurückgestellt und in `BLUEPRINT_ARCHITECTURE.md` als „offener Punkt für PO" vermerkt.

## Teststand

- 64 Tests aus MISSION 12/13 unverändert grün.
- 24 neue Remediation-Tests in `tests/test_remediation.py`.
- **Gesamt: 88 Tests grün** (`pytest tests/ -q`).
