# ADR-01 · Katalog als Python-Code statt JSON oder DB-Konfiguration

Status: Angenommen · Datum: 2026-11-02 · Scope: `app/blueprint/catalog.py`

## Kontext

Blueprint benötigt einen Katalog von Diagnose-Bereichen und Verbesserungs-
Modulen. Mögliche Speicherorte: (a) Python-Dataclasses im Quellcode,
(b) JSON im Repository, (c) separate DB-Tabelle mit Admin-UI.

## Entscheidung

Der Katalog lebt als `@dataclass(frozen=True)` in `app/blueprint/catalog.py`.
Jede Katalog-Änderung ist ein Commit; die aktive Version wird über
`CATALOG_VERSION` als Konstante geführt und zusätzlich auf jedem erstellten
Diagnose-Profil persistiert (siehe ADR-03).

## Alternativen und Verwerfungsgründe

- **JSON im Repo**: Erzwingt zusätzliche Validierung zur Laufzeit;
  Tippfehler in Codes bleiben unentdeckt bis zur Produktion; keine
  IDE-Autovervollständigung. Keine zusätzliche Dependency wie `pydantic`
  erwünscht.
- **DB-Tabelle mit Admin-UI**: Erzeugt eine zweite Quelle der Wahrheit
  (Code ↔ DB), öffnet Angriffsvektor über die UI, erfordert Migrationen.
  Produktvorgabe ist ausdrücklich „nicht-editierbar durch Nutzer".

## Konsequenzen

- Katalog-Erweiterungen erfordern einen Entwickler-Pull-Request.
- Reproduzierbarkeit alter Reports erfordert Historisierung durch
  `catalog_version` (ADR-03).
- Keine Admin-Oberfläche; UI bleibt übersichtlich und auditierbar.
