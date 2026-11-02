# Software Architect Review — Blueprint Design Draft

Durchgeführt: 2026-11-02, read-only.

## Entscheidungen

- **Modul-Layout**: `app/blueprint/` als Unterpaket (`routes.py`, `catalog.py`, `gap.py`; `models.py` nur wenn DTOs entstehen). `main.py` ist bereits ~1160 Zeilen → flat-inline nicht tragfähig.
- **Routen**: `APIRouter(prefix="/blueprint")` via `app.include_router(...)` in `create_app()`. Globale Exception-Handler wirken automatisch. `ctx`-Helper duplizieren oder extrahieren.
- **Katalog**: Python-Datenstruktur (`@dataclass(frozen=True)` oder TypedDict). Keine JSON-Dependency, Linter-Fehler bei Tippfehlern, git-versioniert. Nicht editierbar — passend zur Vorgabe.
- **Schema-Addition**: `CREATE IF NOT EXISTS` idempotent, keine Migration. Vorsicht: `init_db()` hat Backfill-Zeile für `order_contacts` — neue Statements danach eintragen.

## Konkrete Risiken

- `UNIQUE (profile_id, area_code)` → `IntegrityError` bei zweitem POST wird vom globalen Handler als generische 409 gerendert. **Lösung**: `INSERT … ON CONFLICT DO UPDATE` (Upsert) direkt in der Route.
- `created_by INTEGER NOT NULL REFERENCES users(id)` ohne `ON DELETE` kann spätere User-Deaktivierung blockieren. **Lösung**: `ON DELETE RESTRICT` explizit oder nullable.
- `CHECK(status IN …)` hartcodiert; Erweiterung erfordert Schema-Edit → dokumentieren.

## Namensraum-Konflikte

Keine. `/blueprint/*` kollidiert nicht mit bestehenden Pfaden. `TrustedHostMiddleware`, `SessionMiddleware`, `local_boundary` werden geerbt.

## Fehlendes im Entwurf

1. **CSRF**: `local_boundary` wehrt Cross-Origin ab, aber kein CSRF-Token im Formular. Session-Cookies nicht explizit `SameSite=Strict`. Zu dokumentieren.
2. **Audit-Log** über `access_log`: Entwurf schweigt zum Erstellen/Lesen/Löschen. Konvention: `blueprint.profile.create`, `blueprint.profile.view`, `blueprint.profile.delete`.
3. **Löschung + Export**: `DELETE /blueprint/diagnose/{id}` fehlt. `ON DELETE CASCADE` ist DB-seitig definiert, aber kein Route-Pfad.
4. **Idempotenz** auf POST (optional, weil Formular-UI; nicht so kritisch wie `/call/submit`).
5. **Katalog-Versionierung**: Reports reproduzierbar? → `catalog_version` TEXT in `diagnostic_profiles`.

## ADR-Kandidaten

- **ADR-01**: Katalog als Code (Python).
- **ADR-02**: Blueprint-APIRouter statt inline in `create_app()`.
- **ADR-03** (optional): Katalog-Version pro Profil persistieren.

## Offen

- `_home_for(owner)` → bleibt `/dashboard`?
- Reicht `require_strict("owner")` oder liest `confirmer` mit?
- Mehrere Profile pro Betreiber?

Vollständiger Dialog in agent-ID af681303e59534085.
