# Blueprint — Finale Architektur (MISSION 12)

Status: *Entwurf nach Reviews der Spezialisten Product, Software Architecture, UX, Privacy (2026-11-02).* Reality-Check steht aus.

Grundlage: PR #8 Commit `c472d3b` (MISSION 10 Demo Release).

**Korrektur (MISSION 14):** Die ursprüngliche Behauptung „MISSION 11 betrifft
nur Runner-Infra" ist falsch. Der gespeicherte Patch
`feat/autonomous-takeover-hardening` (Commit `7784750`) enthält
App-Änderungen an `app/main.py` und mehreren Templates. In MISSION 14 wurde
der Patch geprüft und *nicht* automatisch übernommen, weil er auf einem
anderen Branch-Zweig liegt und D08 (Failed-Delivery-Recovery) nicht
hinreichend adressiert. D08 wurde stattdessen frisch implementiert; siehe
`MISSION_13_CLOSURE_MATRIX.md`.

## 1. Produkt-Scope

Blueprint ersetzt kein Restaurant-System. Es ist eine lokale Demo- und Diagnoseplattform mit drei Modi (DEMO · DIAGNOSE · PROPOSAL), die (a) ein Referenz-Restaurant zeigt, (b) die real genutzten Werkzeuge und Prozesse eines Betreibers erfasst, (c) einen druckbaren Verbesserungsvorschlag als Diskussionsgrundlage erzeugt. Zielkäufer sind deutsche Lieferrestaurants, Nutzer sind Klare-KI-Vertriebsmitarbeiter in der `owner`-Rolle.

## 2. Modul-Layout

```
app/
  blueprint/
    __init__.py       # exportiert router
    routes.py         # APIRouter(prefix="/blueprint")
    catalog.py        # DIAGNOSE_AREAS + IMPROVEMENTS (frozen dataclasses)
    gap.py            # pure Berechnung: Diagnose + Katalog -> Vorschlagsliste
    redact.py         # Freitext-Redactor (Regex)
  templates/
    blueprint/
      overview.html, demo.html, diagnose_list.html, diagnose_new.html,
      diagnose_profile.html, diagnose_area.html,
      proposal.html, report.html
tests/
  test_blueprint_rbac.py
  test_blueprint_profile.py
  test_blueprint_gap.py
  test_blueprint_report.py
```

Registrierung in `app/main.py` innerhalb `create_app()` via `app.include_router(blueprint.router)`. Die bestehenden Exception-Handler, `SessionMiddleware`, `TrustedHostMiddleware`, `local_boundary` wirken automatisch mit.

## 3. Datenmodell (Erweiterung von `db.SCHEMA`)

```sql
CREATE TABLE IF NOT EXISTS diagnostic_profiles (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  restaurant_name TEXT    NOT NULL,
  city            TEXT    NOT NULL DEFAULT '',
  cuisine         TEXT    NOT NULL DEFAULT '',
  locations_count INTEGER NOT NULL DEFAULT 1 CHECK(locations_count >= 1),
  contact_person  TEXT    NOT NULL DEFAULT '',
  contact_role    TEXT    NOT NULL DEFAULT '',
  status          TEXT    NOT NULL DEFAULT 'draft'
                    CHECK(status IN ('draft','review','shared')),
  catalog_version TEXT    NOT NULL,
  created_by      INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS diagnostic_findings (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id    INTEGER NOT NULL REFERENCES diagnostic_profiles(id) ON DELETE CASCADE,
  area_code     TEXT    NOT NULL,
  status        TEXT    NOT NULL
                  CHECK(status IN ('available','partial','manual','missing','unknown')),
  current_tool  TEXT    NOT NULL DEFAULT '',
  quality       INTEGER CHECK(quality IS NULL OR quality BETWEEN 1 AND 5),
  automation    INTEGER CHECK(automation IS NULL OR automation BETWEEN 1 AND 5),
  time_loss_min_per_day INTEGER
                  CHECK(time_loss_min_per_day IS NULL OR time_loss_min_per_day >= 0),
  verified      INTEGER NOT NULL DEFAULT 0 CHECK(verified IN (0,1)),
  notes         TEXT    NOT NULL DEFAULT '',
  updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  UNIQUE (profile_id, area_code)
);

CREATE TABLE IF NOT EXISTS diagnostic_selections (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id        INTEGER NOT NULL REFERENCES diagnostic_profiles(id) ON DELETE CASCADE,
  improvement_code  TEXT    NOT NULL,
  selected          INTEGER NOT NULL DEFAULT 1 CHECK(selected IN (0,1)),
  priority          TEXT    NOT NULL DEFAULT 'medium'
                      CHECK(priority IN ('low','medium','high')),
  notes             TEXT    NOT NULL DEFAULT '',
  UNIQUE (profile_id, improvement_code)
);
```

Alle `CREATE IF NOT EXISTS`. Keine Migration bestehender Daten.

### Minimierung

Pro Privacy-Review gestrichen: `seats`, `monthly_orders_estimate`, `owner_notes`. Freitext bleibt auf `notes` pro Finding/Selection beschränkt, serverseitiges Längenlimit 500, Regex-Redactor für Telefon/E-Mail/IBAN.

### Upsert-Pattern

Findings und Selections werden per `INSERT INTO ... ON CONFLICT(profile_id, area_code) DO UPDATE SET …` geschrieben — keine `IntegrityError`-Exposition über die generischen Exception-Handler.

## 4. Katalog (Python, versioniert)

`app/blueprint/catalog.py` exportiert `CATALOG_VERSION = "2026-11-02"`, `DIAGNOSE_AREAS: tuple[Area, ...]`, `IMPROVEMENTS: tuple[Improvement, ...]`. Jede Verbesserung trägt:

- `code`, `title`, `problem`, `proposal`
- `preserved_systems`: Liste erhaltener Bestandsmodule
- `required_integrations: tuple[Integration]` mit `verified: bool = False` je Eintrag
- `possible_tools: tuple[Tool]` mit `third_party: bool`
- `complexity`: `low|medium|high`
- `budget_eur_from`, `budget_eur_to` (Richtwert, nie als Angebot deklariert)
- `expected_effect`: Fließtext mit Label „zu validieren"
- `requires_verification`: Liste Annahmen, die vor Umsetzung bestätigt werden müssen
- `addresses_area_codes`: welche Diagnose-Bereiche abgedeckt werden

Newo erscheint ausschließlich unter `possible_tools` mit `third_party=True` und `verified=False`.

## 5. Diagnose-Bereiche (12)

| Code | Titel (deutsch) |
|---|---|
| `pos` | Kassen- und Bestellsystem |
| `payments` | Zahlung, TSE und GoBD |
| `delivery_platforms` | Lieferplattformen |
| `phone` | Telefonie und Anrufannahme |
| `online_orders` | Online-Bestellungen (eigene Kanäle) |
| `kitchen` | Küchenorganisation |
| `couriers` | Fahrer und Dispatch |
| `crm` | Stammkunden und Rückgewinnung |
| `analytics` | Berichte und Kennzahlen |
| `menu_compliance` | Speisekarte und LMIV (Allergene) |
| `accounting` | Buchhaltung und DATEV-Export |
| `manual_ops` | Manuelle Betriebsprozesse |

## 6. Verbesserungs-Katalog (9 Module)

`ai_phone_reception`, `unified_order_intake`, `kds`, `delivery_mgmt`, `crm_automation`, `owner_analytics`, `staff_automation`, `review_mgmt`, `workflow_automation`. Mapping auf Bereiche erfolgt in `catalog.py` via `addresses_area_codes`.

## 7. Gap-Logik (`gap.py`)

Reine Berechnung ohne DB-Zugriff:

- `missing` → Vorschlag mit `priority='high'`
- `manual` → `priority='medium'`
- `partial` → `priority='low'`
- `available` → nicht vorgeschlagen (es sei denn `verified=0`, dann als „Verifikation empfohlen" eigene Rubrik)
- `unknown` → Rubrik **„Zunächst klären"** (nicht Lücke)

Keine Addition von Zeitersparnissen ohne Label.

## 8. Routen

| Methode & Pfad | Rolle | Zweck |
|---|---|---|
| `GET  /blueprint` | eingeloggt | Übersicht + Einstieg |
| `GET  /blueprint/demo` | eingeloggt | Referenz-Narrativ |
| `GET  /blueprint/diagnose` | owner | Profilliste |
| `GET  /blueprint/diagnose/new` | owner | Neues Profil-Formular |
| `POST /blueprint/diagnose/new` | owner | Profil anlegen |
| `GET  /blueprint/diagnose/{id}` | owner | Profilübersicht + Fortschritt |
| `GET  /blueprint/diagnose/{id}/area/{code}` | owner | Bereichsformular |
| `POST /blueprint/diagnose/{id}/area/{code}` | owner | Bereich upserten |
| `POST /blueprint/diagnose/{id}/status` | owner | Statuswechsel draft/review/shared |
| `POST /blueprint/diagnose/{id}/delete` | owner | Löschen |
| `GET  /blueprint/proposal/{id}` | owner | Vorschlagsliste (Auswahl) |
| `POST /blueprint/proposal/{id}/select` | owner | Auswahl speichern |
| `GET  /blueprint/proposal/{id}/report` | owner | Druckfähiger HTML-Report |

Alle Mutationen loggen in `access_log` mit Konvention `blueprint.<entity>.<verb>`.

## 9. UI

Topbar bekommt EINEN Blueprint-Link (owner only). Innerhalb von `/blueprint` gibt es eine Sub-Nav (Demo · Diagnose · Vorschlag · Bericht).

Status-Badge-Modifikatoren neu: `.status-badge--available`, `--partial`, `--manual`, `--missing`, `--unknown` (letztere mit Label **„Noch zu klären"**). `print-color-adjust: exact` für Chips.

Diagnose: pro Bereich eine eigene Seite, Fortschrittsbalken „X von 12".

Hinweis auf jedem Finding-Formular: „Nur betriebsbezogene Hinweise. Keine Namen, Telefonnummern, E-Mails."

## 10. Report

`report.html` extends eine schlanke `print_base.html` ohne Topbar. Pflicht-Fußzeile:

> Vertraulich — interne Angebotsvorbereitung Klare KI. Nicht zur Weitergabe an Dritte. Erstellt am {Datum} von {Benutzer}. Zahlen mit Label „Schätzung" oder „Richtwert" sind unverbindlich.

Jeder Vorschlag im Report trägt sichtbar das Label der Katalog-Version und die Markierung „Zu bestätigen vor Umsetzung".

## 11. Tests

Alle Blueprint-Tests leben in einer gemeinsamen Datei `tests/test_blueprint.py`
(bewusst zusammengefasst, da die Fixtures und Helper gleich bleiben; die
einzelne Datei bleibt übersichtlich und wird vom gleichen `tmp_db`-Fixture
isoliert). Abgedeckt sind:

- RBAC auf Diagnose/Proposal (403 für Kitchen/Confirmer/Courier).
- Profil-CRUD, Area-Upsert-Idempotenz, Status-Transitionen.
- **Löschkaskade**: Profil-Delete entfernt Findings + Selections (verifiziert
  `PRAGMA foreign_keys=ON`).
- Gap-Logik: `unknown` erzeugt keine Lücke, `available` wird nicht
  vorgeschlagen (außer `verified=0` → Rubrik „Verifikation empfohlen"),
  `missing` → `high`.
- Vorschlagsauswahl + Report-Pflichtinhalte (Katalog-Version, Vertraulichkeits-
  Fußzeile, „Richtwert — nicht Angebot").
- Freitext-Redaktion mit Audit-Log-Eintrag und False-Positive-Schutz.
- Audit-Log-Einträge für Profil-Create/Delete.
- Reine Unit-Tests der `gap.analyze`-Funktion.

Baseline: 40 bestehende Tests (`test_e2e_flow.py`, `test_demo_release.py`,
`test_hardening.py`) bleiben unverändert und grün. Nach den Reality-Check-
Fixes: **64 Tests grün** insgesamt.

## 12. ADR-Kandidaten (siehe `docs/blueprint/adr/`)

- **ADR-01**: Katalog als Python-Code, nicht JSON/DB.
- **ADR-02**: Blueprint als `APIRouter` in Unterpaket `app/blueprint/`.
- **ADR-03**: `catalog_version` pro Profil persistieren (Report-Reproduzierbarkeit).

## 13. Bestätigte vs. Unbestätigte Integrationen

Siehe `docs/blueprint/INTEGRATIONS.md`. Alle derzeit **unbestätigt**. Keine POS/CRM/Telefon-API wurde technisch verifiziert.

## 14. Reality-Check-Ergebnisse (nach Durchführung)

Der Reality-Checker (Agent-ID a116d53630ee61237, 2026-11-02) hat das Paket
unabhängig geprüft. Verdikt: **NEEDS WORK** — Kernzusagen akzeptabel,
mehrere Lücken behoben:

- Formulierung „Bauchgefühl" im Katalog neutralisiert.
- Löschkaskaden-Test ergänzt (`test_profile_delete_cascades_findings_and_selections`).
- `test_overview_requires_login` auf konkreten Statuscode festgenagelt.
- `test_unknown_is_not_a_gap` auf strikten Negativ-Check verschärft.

Bewusst unerledigt (dokumentiert, nicht fehlerhaft):

- Automatisierte Browser-Druckprüfung nicht möglich — nur HTTP/HTML
  geprüft, als „experimentell" markiert.
- `aria-live`-Fokus-Management im Formular wurde zugunsten des reinen
  303-Redirects verworfen; für eine spätere A11y-Iteration vorgemerkt.
- Vergleichsspalte „Referenz (DEMO) vs. Ihr Betrieb" im Report nicht
  umgesetzt — die Ist-Tabelle enthält bereits Status pro Bereich, eine
  Zusatzspalte folgt bei Bedarf.
- Codex-Zweitprüfung in `outputs/codex/` pending — nur bei autorisierter
  separater Codex-Sitzung.

## 15. Mandanten-Isolation

Innerhalb der `owner`-Rolle sehen alle Nutzerinnen und Nutzer alle Diagnose-
Profile. Dies ist eine bewusste Entscheidung: Blueprint ist ein internes
Vertriebswerkzeug der Klare KI, nicht ein von-Betreibern-selbst-bedienter
Dienst. Eine spätere Multi-Mandanten-Erweiterung bleibt möglich und ist
nicht Teil dieses MVP.
