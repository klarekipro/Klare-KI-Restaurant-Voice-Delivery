# Reality-Checker Review — Blueprint Package

Durchgeführt: 2026-11-02, read-only, unabhängig (nicht an Erstellung beteiligt).
Verdikt: **NEEDS WORK** (akzeptable Kernzusagen, aber mehrere Lücken).

## Als korrekt bestätigt

- `catalog_version` pro Profil persistiert, in UI und Report sichtbar.
- Löschroute `POST /blueprint/diagnose/{pid}/delete` mit RBAC und Audit-Eintrag.
- Audit-Log-Konvention eingehalten.
- Freitext-Redactor: Regex-Entfernung, Audit-Hits ohne PII in `reason`.
- Report-Pflichtfußzeile vorhanden.
- RBAC auf allen schreibenden Blueprint-Routen.
- Keine ROI-/Minuten-Versprechen im Katalog.

## Abweichungen (nach Fix)

| Abweichung | Status nach Fix |
|---|---|
| Testdatei als Sammeldatei statt 5 getrennt | Dokumentiert in BLUEPRINT_ARCHITECTURE.md (Abschnitt 11 aktualisiert) |
| Formulierung „Bauchgefühl" in Owner-Analytik | **behoben** in `catalog.py` → „beruhen auf Erfahrung ohne tägliche Kennzahlen" |
| `test_overview_requires_login` zu tolerant | **behoben**: fixer 303 + Location-Check |
| `test_unknown_is_not_a_gap` zu schwach | **behoben**: strikter Negativ-Check |
| Kein Test für Löschkaskade | **behoben**: `test_profile_delete_cascades_findings_and_selections` |
| ADR- und INTEGRATIONS-Dateien erwähnt, aber vom Checker nicht gelesen | ADR-01…03 + INTEGRATIONS.md jetzt im Repo (zu sehen) |
| UX-Punkt `aria-live` + Vergleichsspalte DEMO vs. Ist | **nicht umgesetzt**, als bewusste Vertagung dokumentiert |
| Mandanten-Entscheidung „alle Owner sehen alle Profile" | **dokumentiert** in Architektur-Doku |

## Risiken, die bestehen bleiben

- **Browser-Druckprüfung** nicht automatisiert möglich; nur HTTP/HTML geprüft.
- **Phone-Regex** kann theoretisch false-positive sein (z. B. lange Datumsreihen);
  Mindestlängen-Filter senkt das Risiko und ist durch
  `test_notes_short_fragment_is_not_redacted` abgesichert.
- **DSGVO-Rechtsprüfung** steht aus (unverändert gegenüber Privacy-Review).

## Formulierungs-Korrekturen (umgesetzt)

- `catalog.py` Owner-Analytik `problem`: neutraler formuliert.
- „40 Tests grün" durch exakte Zahlen ersetzt: 40 bestehende Tests + 24 neue
  Blueprint-Tests = **64 grün** nach den Reality-Checker-Fixes.

## Offen gelassen

- Codex-Zweitprüfung in `outputs/codex/`: **pending**. Keine autorisierte
  separate Codex-Sitzung wurde gestartet.
- Mehrfach-Profile pro Betreiber: zulässig per Design, keine zusätzliche
  Logik — eine spätere ADR könnte dies formalisieren.

Vollständiger Dialog in agent-ID a116d53630ee61237.
