# Product Manager Review — Remediation Plan

Durchgeführt: 2026-11-02, agent-ID a0ec5938e82d3073e.

## Zentrale Lücken des Plans
1. **Katalog-Daten nicht umgeschrieben** — Plan überlagert nur im Template. `preserved_systems=("Vorhandene Küche-Oberfläche (/kitchen)" ...)` und `possible_tools=("Erweiterung der MVP-...", third_party=False)` sowie „Vor externem CRM bevorzugen" müssen aus `catalog.py` selbst entfernt werden. Sonst erneuter D10 Fail.
2. **Fehlender `not_applicable` Status**: Diagnose kennt nur 5 Status; Codex-Szenario B („keine eigenen Fahrer") ist nicht ausdrückbar. Zusätzlich fehlen Katalog-Felder `requires_own_delivery`, `requires_own_phone_channel`, `requires_direct_online_channel`.
3. **Schwelle „kein Bedarf"** zu lax: `≥10/12 beantwortet` erlaubt kritische Lücken.
   - Alle 12 + 0 Vorschläge + 0 unknown in Kernbereichen (pos, payments, phone, kitchen) → „kein Bedarf".
   - 1–3 unknown in Nicht-Kernbereichen → „kein akuter Bedarf; folgende Punkte offen".
   - ≥ 1 unknown in Kernbereichen → „Diagnose unvollständig — nicht entscheidungsreif".
4. **Kein harter „No-Audit-CTA"**-Guardrail im not-needed-Ausgang.
5. **Scoring unentschieden**: Entweder Regel ODER manuell — PO entscheiden. Empfehlung: Evidence-Zählung statt Dringlichkeit; „Priorität" rein als Vorschlag kennzeichnen.
6. **Preserved-Systems-Fallback** bei leerem `current_tool`:
   - leer + available/partial → „Vom Betrieb bestätigtes System, Name nicht erfasst"
   - leer + manual/missing → „Kein Werkzeug im Einsatz"
   - niemals MVP-Pfade einsetzen.

## Konkret zu entschärfende Katalog-Texte
- `unified_order_intake.proposal`: „Doppelerfassung entfällt" → „kann je nach POS-Schnittstelle und Plattform-Freigabe reduziert werden".
- `kds.proposal`: „Die bestehende Küche-Oberfläche aus dem MVP ist Ausgangspunkt" → neutrale Formulierung ohne MVP-Verweis.
- `delivery_mgmt.proposal`: nicht Umbau einer Klare-KI-Oberfläche unterstellen; Optionen in Reihenfolge Bestandssystem→Markt→Eigenbau.
- `crm_automation.possible_tools`: „Vor externem CRM bevorzugen" ersatzlos streichen.

## Fehlendes mit FAIL-Risiko bei Codex-Zweitlauf
1. Katalog-Daten MVP-zentrisch (D10 wiederkommend).
2. Kein `not_applicable` Status + fehlende Applicability-Felder (D03 wiederkommend).
3. D06-Ausgang ohne „kein Audit-CTA"-Regel.
4. D04 unentschieden.
5. D07 Evidence-Rendering, besonders Freitext-XSS/PII-Risiko, nicht spezifiziert.

Vollständige Rückgabe in Agent-ID a0ec5938e82d3073e.
