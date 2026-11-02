# UX Architect Review — Blueprint Design Draft

Durchgeführt: 2026-11-02, read-only.

## Entscheidungen
- **Navigation**: 1 Topbar-Link „Blueprint" (nur `owner`), interne Sub-Navigation (Tabs Demo · Diagnose · Vorschlag · Bericht) unter `/blueprint`.
- **Flow**: frei, aber „empfohlener nächster Schritt"-CTA; PROPOSAL rendert leeren Zustand bis mind. N Bereiche beantwortet.
- **Diagnose-Fragebogen**: Pro Bereich eine Seite mit Fortschrittsbalken (X von 12). Autosave-Einheit + „Speichern & nächster Bereich"-Button.
- **Status-Chip-Mapping**:
  - `available` → grün (wie `--delivered`), Icon ✓
  - `partial` → amber (wie `--en-route`), Icon ◐
  - `manual` → warn (wie `--new`), Icon ⚙
  - `missing` → rot (wie `--failed`), Icon !
  - `unknown` → neutral-grau, Icon ?, Label **„Noch zu klären"** (nicht „Unbekannt")
- **Unknown**: eigener Report-Abschnitt „Zunächst klären", nicht als Lücke gezählt.

## Print-CSS (nicht verhandelbar)
1. `@page { margin: 18mm 15mm 22mm 15mm; }` + `break-inside: avoid` auf Abschnitte.
2. `print-color-adjust: exact;` auf Chips und Badges.
3. Seiten-Footer via `@page @bottom-right` (Seite x/y + Datum + Profilname). Fallback nötig falls Browser unsupported.

## Barrierefreiheit
- Fokus-Management nach POST: `aria-live="polite"` + Fokus auf „Nächster Bereich"-Button.
- Status als `<fieldset>` + `radio`, `:focus-visible` outline, Kontrast-AA Prüfung der Pastell-Chips.

## Fehlendes im Entwurf
- **Profil-Status**: `draft → review → shared` zur Unterscheidung Entwurf/finales Gespräch.
- **Vergleichs-Spalte**: Report muss „Referenz (DEMO) vs. Ihr Betrieb" pro Bereich zeigen.

## Offene Fragen
- Eigene Rolle `sales` oder weiter `owner`?
- Mehrere Profile pro Kunde erlaubt?

Vollständiger Dialog in agent-ID ad93ade187e0c918b.
