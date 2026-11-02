# ADR-02 · Blueprint als APIRouter in Unterpaket `app/blueprint/`

Status: Angenommen · Datum: 2026-11-02 · Scope: `app/blueprint/`, `app/main.py`

## Kontext

Blueprint fügt 13 Routen zur bestehenden FastAPI-Anwendung hinzu. Die
vorhandene `app/main.py` enthält bereits ~1160 Zeilen inline-Routen in
`create_app()`. Weitere Routen inline hinzuzufügen würde die Datei auf über
1500 Zeilen bringen und die bereits etablierte Modul-Trennung
(`auth`, `db`, `orders`, `seed`, `voice/*`) brechen.

## Entscheidung

Blueprint ist ein eigenes Unterpaket `app/blueprint/` mit `routes.py`,
`catalog.py`, `gap.py`, `redact.py`. Der `APIRouter(prefix="/blueprint")` wird
in `create_app()` per `app.include_router(blueprint_router)` registriert.
Templates liegen unter `app/templates/blueprint/*.html`.

## Konsequenzen

- Konsistenz mit bestehender Modul-Trennung bleibt gewahrt.
- Globale Exception-Handler, `SessionMiddleware`, `TrustedHostMiddleware`
  und `local_boundary` werden geerbt.
- Jinja2-Filter werden über das gemeinsame Modul `app/formatting.py` in
  beide `Jinja2Templates`-Instanzen eingehängt (`main` und `blueprint`), um
  einen zirkulären Import zu vermeiden.
- Der Preis ist eine zweite `Jinja2Templates`-Instanz; der Vorteil ist, dass
  Blueprint seinen eigenen Namensraum (`bp_status_de`, `bp_status_chip`,
  `bp_priority_de`) sauber hält.
