# Closure-Matrix — MISSION 15 Blocker → Remediation (MISSION 16)

Grundlage: Codex MISSION 15 FAIL-Verdikt auf PR #10 (`53baebe181a…`), siehe
`REMAINING_BLOCKERS.md`, `D01_D10_CLOSURE_MATRIX.md`, `BUSINESS_SCENARIOS.md`
und `FINAL_ACCEPTANCE_REPORT.md`.

Diese Matrix listet pro Codex-Blocker die konkrete Code-Änderung und die
Regression. Keine Behauptung einer eigenen Zweitabnahme — die bleibt für
eine neue Codex-Sitzung reserviert.

## R1–R7

| Codex-ID | Problem | Fix (Code) | Regressionstest |
|---|---|---|---|
| **R1 (P1)** — `_strong_pain` nahm `automation≤2` allein als Beweis für Belastung | `app/blueprint/applicability.py` `_strong_pain`: automation-Score entfernt. Pain nur bei `quality≤2` ODER `time_loss≥60` ODER affirmativem Problem-Keyword in notes. `_staff_automation` liefert `not_applicable` statt `conditional`, wenn ein manueller Prozess ohne gemessene Belastung bleibt. | `test_R1_healthy_manual_is_not_required[phone/kitchen/crm/manual_ops]` |
| **R2 (P1)** — `no_need` ignoriert bestätigte Probleme ohne Katalog-Match (payments/analytics) | Neue `ProblemArea` + `GapResult.problems` + `problems_without_match` in `gap.py`. Neuer `outcome="problems_without_match"` wird in `report.html` und `proposal.html` eigenständig gerendert. Kein fiktiver Katalog-Eintrag für Zahlung. | `test_R2_explicit_core_payment_gap_is_not_no_need`, `test_R2_available_analytics_with_pain_is_not_no_need`, `test_report_renders_problems_without_match_outcome` |
| **R3 (P2)** — Review-Keyword ohne Negationskontrolle | `_review_mgmt` + neuer Helfer `_notes_signal_problem` mit `_NEGATION_PATTERNS` + `_PROBLEM_KEYWORDS`. Nur affirmierte Probleme triggern `conditional`; „Keine Probleme" oder „werden beantwortet" wird respektiert. | `test_R3_negated_review_note_does_not_create_problem`, `test_R3_affirmative_review_problem_still_triggers` |
| **R4 (P1)** — Evidence meldet `Status: teilweise` für `available`-Input | `_ai_phone_reception`, `_kds`, `_crm_automation` erhalten explizite `available + strong_pain`-Verzweigung mit Evidence „Status: vorhanden mit genannter Belastung". | `test_R4_phone_evidence_does_not_invent_partial_status`, `test_evidence_mirrors_input_time_and_quality` |
| **R5 (P2)** — Status-only unverified missing bekam Confidence `high` | Neuer Helfer `_calibrated_confidence(finding, baseline)`: `high` nur bei `verified=1` oder messbaren Daten/Notizen. Angewandt in allen Rules. Bestehender Test `test_gap_unit_missing_phone_proposes_high` auf das korrekte Verhalten umgezogen (medium für bare missing, high für verified missing). | `test_R5_status_only_unverified_missing_is_not_high_confidence`, `test_R5_verified_missing_keeps_high_confidence`, aktualisierter `test_gap_unit_missing_phone_proposes_required_with_verified_high_confidence` |
| **R6 (P2)** — Legacy `selected=0 priority=medium` Zeilen bekamen `priority_source='manual'` und überrollten neue Engine-highs | `app/db.py` `_ensure_selections_priority_source`: ALTER TABLE default auf `'auto'`, zusätzlich idempotentes `UPDATE … SET priority_source='auto' WHERE selected=0`. `routes.proposal_view` und `proposal_report` filtern manuelle Overrides zusätzlich nach `selected=1`. | `test_R6_legacy_unselected_overrides_do_not_survive` (lädt echtes MISSION-12-Schema aus `git show 53d04a5:app/db.py`) |
| **R7 (P2)** — SQL las `state.failed_delivery`, Writer schrieb `status.failed_delivery` | `app/main.py` Dispatch-Query auf `'status.failed_delivery'` korrigiert (Zeilen 701/704). | `test_R7_failed_delivery_reason_and_timestamp_visible`, `test_R7_failed_reason_is_html_escaped`, `test_R7_failed_reason_hidden_from_wrong_roles[kitchen/courier1]` |

## Pflicht-Szenarien A–H

| Szenario | Erwartetes Ergebnis | Test |
|---|---|---|
| **A** — Ruhiges manuelles Chaos (quality=1, time>60) | `has_findings`, Vorschläge für phone/kitchen/dispatch | `test_scenario_A_manual_with_losses_gives_recommendations` |
| **B** — Lightspeed POS + Lieferando, keine eigenen Fahrer | `delivery_mgmt` → `not_applicable` mit Grund „Plattformen" | `test_scenario_B_platform_only_hides_dispatch_module` |
| **C** — Vollständig automatisiert | `no_need`, keine Suggestions, keine Probleme | `test_scenario_C_fully_automated_is_no_need` |
| **D** — Gesunder manueller Prozess (zero loss, quality=5) | KEIN `required`; akzeptabel ist nur `conditional/low` | `test_scenario_D_healthy_manual_zero_loss_is_not_sold` |
| **E** — Zahlungen fehlen, kein Katalog-Modul | `outcome=problems_without_match`, Problemliste zeigt `payments` | `test_scenario_E_payments_problem_without_catalog_match` |
| **F** — Widersprüchliche / unvollständige Daten | Confidence nicht `high`; kein `required` bei leeren Feldern | `test_scenario_F_contradictory_data_lowers_confidence`, `test_scenario_F_incomplete_signals_do_not_fire_required` |
| **G** — Legacy-Profil nach Migration | Neue Engine-high überlebt alte medium-Overrides | `test_R6_legacy_unselected_overrides_do_not_survive` |
| **H** — Failed delivery mit Grund-Text | Grund + Zeitstempel sichtbar; HTML-Escaping; RBAC | `test_R7_failed_delivery_reason_and_timestamp_visible`, `test_R7_failed_reason_is_html_escaped`, `test_R7_failed_reason_hidden_from_wrong_roles` |

## Testsummen

- 88 bestehende Tests bleiben grün (davon 1 explizit umgezogen auf R5-korrektes Verhalten).
- 26 neue Tests in `tests/test_mission16.py` (R1–R7 + Szenarien A–H + Evidence-Integrität + Template-Rendering).
- **Gesamt: 114/114 passed** (`pytest tests/ -q` auf Python 3.14 mit dem Projekt-Venv).

## Nicht gemacht (bewusst)

- Keine neuen Produktmodule (z. B. Zahlungen) — Blueprint signalisiert bestätigte Probleme ohne vorzutäuschen, ein Modul zu haben.
- Keine Frontend-Umbauten über die zwei Outcome-Banner hinaus.
- Keine Codex-Zweitabnahme (Pflicht vor Merge, nur in separater autorisierter Codex-Sitzung).
- Keine Browser-/Druck-Verifikation (Werkzeuggrenze, von Codex explizit als NOT VERIFIED markiert).
- Keine Änderungen an Agent-Runner, PR #10 oder anderen Worktrees.
- Keine `force-push`-Operation.
