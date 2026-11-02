# ADR-03 · Katalog-Version pro Profil persistieren

Status: Angenommen · Datum: 2026-11-02 · Scope: `diagnostic_profiles.catalog_version`

## Kontext

Der Katalog (ADR-01) ändert sich im Laufe der Zeit. Reports, die bereits mit
einem Betrieb geteilt wurden, müssen reproduzierbar bleiben, auch wenn
inzwischen neue Verbesserungen aufgenommen oder Beschreibungen geändert
wurden.

## Entscheidung

Jedes Diagnose-Profil speichert bei Anlage den Wert von `CATALOG_VERSION`
in `diagnostic_profiles.catalog_version TEXT NOT NULL`. Alle Reports zeigen
diesen Wert im Kopf und in der Fußzeile.

## Konsequenzen

- Die Spalte ist unveränderlich für die Lebensdauer des Profils; es gibt
  keine Route, die sie nachträglich ändert.
- Für die aktuelle Phase gibt es nur eine Version (`2026-11-02`); echtes
  Freeze-Verhalten greift erst bei einer späteren Katalog-Änderung.
- Falls ein Profil mit einem älteren Katalog angezeigt werden muss (nach
  Katalog-Update), ist eine zusätzliche Lade-Logik erforderlich — vorerst
  ausgeklammert, da nur eine Version existiert; dokumentiert als offener
  Punkt.
