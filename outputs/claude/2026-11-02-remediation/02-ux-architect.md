# UX Architect Review — Remediation Plan

Durchgeführt: 2026-11-02, agent-ID a7d7dd1126583f18b.

## Mobile-Strategie je Blueprint-Tabelle
- `diagnose_list.html` → **Karten-Layout** (Headline-Link + Chip-Zeile)
- `diagnose_profile.html` Bereichs-Tabelle → **Karten-Layout**
- `proposal.html` → **gemischt**: Karte als Container, Checkbox + Select stacked
- `report.html` → **horizontaler Scroll-Container** mit Sticky-Spalte (Druck-Layout bleibt)

Regeln: Breakpoint `max-width: 640px`, blueprint-scoped. Karten mit `data-label` + `clip`-Technik für Screen Reader. Scroll nur in markiertem Container.

## Print
`@media print` setzt Mobile-Overrides zurück — Papier/PDF-Darstellung bleibt Desktop-identisch.

## Profil-Edit
Separater Screen `/blueprint/diagnose/{id}/edit`. Breadcrumb + Flash nach Save.

## Failed-Delivery UI
Eigener Abschnitt in `/dispatch` (nicht separate Route). Pro Zeile: Order-ID, Kunde, Adresse, `status-badge--failed`, Grund + Zeitstempel, **Retry** (Fahrer-Select + Button), **Abbrechen** (destruktiv, Pflicht-Grund ≥ 3 Zeichen). Empty-State: „Keine fehlgeschlagenen Zustellungen".

## Destruktive Aktionen
`button.danger` + nativer `confirm()` mit Order-ID und Konsequenz-Text. Für Abbrechen zusätzlich serverseitig Pflichtfeld `reject_reason`.

## A11y
- Mindest-Touchfläche 44×44 für Blueprint-Interaktion auf < 640 px.
- Kein horizontaler Scroll am Hauptinhalt; Scroll nur in markierten Containern.
- `:focus-visible` Outline (fehlt derzeit komplett in style.css).

## Fehlendes im Plan
1. Keyboard/Screen-Reader (`aria-live` für Flash nach Retry/Cancel, Scope-Attribute im Karten-Transform).
2. UX für 409-Konflikte (jemand hat parallel schon abgebrochen), Edit-Parallelität, D02-Helfertext „0 = keine Zeitverluste, leer = unbekannt", Empty-State der Diagnose-Liste.
3. `reject_reason` ist Freitext mit PII-Risiko → Redactor Pflicht.

Vollständige Rückgabe in Agent-ID a7d7dd1126583f18b.
