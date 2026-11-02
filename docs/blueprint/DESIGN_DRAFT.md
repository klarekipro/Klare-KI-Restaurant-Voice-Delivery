# Klare KI Restaurant Blueprint — Design Draft

Dieses Dokument ist der **Entwurf** für MISSION 12. Spezialisten (Product, Architecture, UX, Privacy, Business) kritisieren und ergänzen ihn. Der endgültige Entwurf lebt in `BLUEPRINT_ARCHITECTURE.md`.

## Zielbild

Blueprint ist eine *Demonstrations- und Diagnoseplattform*. Es ersetzt keine Restaurantsoftware, sondern:

1. zeigt ein Referenzsystem (DEMO),
2. erfasst die tatsächlich genutzten Programme und Prozesse eines Kunden (DIAGNOSE),
3. erstellt einen individuellen Verbesserungsplan ohne erzwungenen Ersatz (PROPOSAL).

## Nicht-Ziele

- Keine Behauptungen über API-Kompatibilität ohne Nachweis.
- Keine fiktiven Umsatz-/ROI-Zahlen.
- Keine Eigenentwicklung eines Sprach-Engines (Newo = *potenzieller* Drittanbieter).
- Keine Produktionsdaten, keine bezahlten APIs, keine externen MCPs.

## Erhaltene Module (unverändert)

Dashboard, Order Management (`/confirmer`), Call Simulator (`/call`), CRM (`/customers`), Menu (`/menu`), Kitchen (`/kitchen`), Dispatch (`/dispatch`), Courier (`/courier`), Auth/RBAC, SQLite, bestehende Tests.

Call Simulator bleibt explizit als Simulator markiert.

## Neue Oberflächen

Alle Routen unter `/blueprint`:

| Route                                         | Rolle              | Zweck                                       |
|-----------------------------------------------|--------------------|---------------------------------------------|
| `GET  /blueprint`                             | eingeloggt         | Übersicht & Einstieg                        |
| `GET  /blueprint/demo`                        | eingeloggt         | Referenz-Restaurant mit Narrativ            |
| `GET  /blueprint/diagnose`                    | owner              | Liste aller Diagnosen                       |
| `POST /blueprint/diagnose/new`                | owner              | Neues Profil anlegen                        |
| `GET  /blueprint/diagnose/{id}`               | owner              | Profilübersicht + Fortschritt               |
| `GET  /blueprint/diagnose/{id}/area/{code}`   | owner              | Formular für einen Bereich                  |
| `POST /blueprint/diagnose/{id}/area/{code}`   | owner              | Antworten speichern                         |
| `GET  /blueprint/proposal/{id}`               | owner              | Vorschlagsliste (Katalog × Diagnose)        |
| `POST /blueprint/proposal/{id}/select`        | owner              | Verbesserungen auswählen                    |
| `GET  /blueprint/proposal/{id}/report`        | owner              | Druckfähiger HTML-Bericht                   |

RBAC: `require_strict("owner")` für Diagnose/Proposal; `require_strict("owner","confirmer","kitchen","courier")` für Demo.

## Datenmodell (neue Tabellen)

```sql
CREATE TABLE diagnostic_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  restaurant_name TEXT NOT NULL,
  city TEXT NOT NULL DEFAULT '',
  cuisine TEXT NOT NULL DEFAULT '',
  seats INTEGER,
  monthly_orders_estimate INTEGER,
  owner_notes TEXT NOT NULL DEFAULT '',
  created_by INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE diagnostic_findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER NOT NULL REFERENCES diagnostic_profiles(id) ON DELETE CASCADE,
  area_code TEXT NOT NULL,                  -- pos, delivery_platforms, phone, …
  status TEXT NOT NULL CHECK(status IN
          ('available','partial','manual','missing','unknown')),
  current_tool TEXT NOT NULL DEFAULT '',    -- Freitext: "Lightspeed K-Series"
  quality INTEGER,                           -- 1..5 oder NULL
  automation INTEGER,                        -- 1..5 oder NULL
  time_loss_minutes_per_day INTEGER,         -- geschätzt, NULL erlaubt
  verified INTEGER NOT NULL DEFAULT 0,       -- techn. verifiziert?
  notes TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (profile_id, area_code)
);

CREATE TABLE diagnostic_selections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER NOT NULL REFERENCES diagnostic_profiles(id) ON DELETE CASCADE,
  improvement_code TEXT NOT NULL,
  selected INTEGER NOT NULL DEFAULT 1,
  priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high')),
  notes TEXT NOT NULL DEFAULT '',
  UNIQUE (profile_id, improvement_code)
);
```

Alle Tabellen `CREATE IF NOT EXISTS`, Schema erweitert über `db.SCHEMA` (keine Migration — reine Addition).

## Katalog (Code-Konfig, kein User-Edit)

`app/blueprint/catalog.py` liefert eine typisierte Datenstruktur:

- 12 **Diagnose-Bereiche** mit Fragen (deutsch).
- 9 **Verbesserungsmodule** (`ai_phone_reception`, `unified_order_intake`, `kds`, `delivery_mgmt`, `crm_automation`, `owner_analytics`, `staff_automation`, `review_mgmt`, `workflow_automation`).
- Jede Verbesserung: Problem, Vorschlag, erhaltene Systeme, nötige Integrationen (mit `verified: false`), mögliche Werkzeuge (mit `third_party: true`), Komplexität (`low/medium/high`), Budget-Range in EUR (Spanne, markiert als Schätzung), zu bestätigende Annahmen.

Keine Integration ist standardmäßig `verified: true`. Newo erscheint nur mit `third_party` und `unverified`.

## Gap-Logik

Für jede Verbesserung ermitteln wir, welche Bereiche sie adressiert. Status-Mapping:

- `missing` → Vorschlag mit hoher Priorität
- `manual` → mittlere Priorität
- `partial` → niedrige Priorität
- `available` → nicht vorgeschlagen (es sei denn `verified = 0`)
- `unknown` → als „Zunächst klären" statt als „fehlt" aufgeführt

Keine Addition von „gesparten Minuten" ohne klares Label *Schätzung, unbestätigt*.

## HTML-Report

Eigenes Template `blueprint_report.html` mit Print-CSS (`@media print`). Der Nutzer verwendet die Druck-Funktion des Browsers zur PDF-Erzeugung. Kein Server-side PDF-Rendering.

## Tests (neu)

- `test_blueprint_rbac.py`: nur owner erreicht Diagnose/Proposal.
- `test_blueprint_profile_crud.py`: Profil anlegen, Bereich beantworten, laden.
- `test_blueprint_gap.py`: `unknown` erzeugt keine fiktive Lücke; `available` wird nicht vorgeschlagen.
- `test_blueprint_report.py`: Report enthält Katalog-Pflichtfelder und das Label „unbestätigt".
- Alle bestehenden Tests bleiben grün.

## Offene Fragen für Spezialisten

- **Product**: Welche 12 Bereiche sind korrekt? Welche Kennzahlen sollte das Profil für ein Verkaufsgespräch tragen?
- **Software Architect**: Addition in `app/blueprint/*` vs. flache Dateien? Catalog als Python-Datenstruktur vs. JSON im Repo?
- **UX**: Flow Demo → Diagnose → Proposal. Soll ein Fortschritts­indikator in der Diagnose zwingend sein?
- **Privacy**: Dürfen wir das Profil samt genutzter POS-/CRM-Namen überhaupt lokal speichern? Reicht Löschbarkeit?
- **Business**: Welche Felder braucht der Report für ein konkretes Angebot (Bedarf, nicht Buzzwords)?

## Explizite Nicht-Verifikations-Mapping

Jede im Report angezeigte Zahl trägt eines dieser Labels:

- **Bestätigt** (nur wenn `verified = 1` manuell gesetzt wurde),
- **Schätzung Betreiber** (vom Owner im Diagnose-Formular angegeben),
- **Richtwert Klare KI** (aus Katalog, markiert als unverbindlich).
