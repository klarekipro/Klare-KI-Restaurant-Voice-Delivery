# Privacy Engineer Review — Blueprint Design Draft

Durchgeführt: 2026-11-02, read-only.

## DSGVO-Kategorien

- Personenbezogen (Kontext): `restaurant_name` (Inhabername häufig), `city` kombiniert, `created_by` (Beschäftigtendaten § 26 BDSG), `owner_notes` / `notes` (Freitextrisiko).
- Nicht personenbezogen: `cuisine`, `seats`, `monthly_orders_estimate`, `area_code`, `status`, `quality`, `automation`.
- Freitext-Risiko: `owner_notes`, `notes`, `current_tool`.

## Rechtsgrundlage
Art. 6 Abs. 1 lit. f/b DSGVO für Angebotsanbahnung + § 26 BDSG für Mitarbeiter. Qualifizierte Rechtsprüfung erforderlich. UI-Pflichthinweis vor Speichern.

## Minimierung — zu streichen

- `seats`, `monthly_orders_estimate` (optionalisieren oder streichen).
- `owner_notes` streichen (redundant mit per-area notes).
- `current_tool`: besser Dropdown + „Sonstiges".
- `created_at`/`updated_at` doppelt — eins behalten + Audit via `access_log`.

## Löschung
`POST /blueprint/diagnose/{id}/delete` für Owner, `ON DELETE CASCADE` greift (Pragma ist bereits aktiv). Audit via `access_log` ohne Payload.

## Audit-Log-Konventionen
`blueprint.profile.create|update|delete`, `blueprint.finding.upsert`, `blueprint.selection.update`, `blueprint.report.render`. `object_id` = Profil-ID. **Keine Inhalte** in `reason`.

## Report-Fußzeile (Pflicht)
> Vertraulich — interne Angebotsvorbereitung Klare KI. Angaben eines befragten Betreibers. Nicht zur Weitergabe an Dritte. Erstellt am {Datum} von {Benutzer}. Zahlen mit Label „Schätzung" oder „Richtwert" sind unverbindlich.

## Freitext-Mitigation (technisch)
1. Serverseitiges Zeichenlimit (z. B. 500) pro Freitextfeld.
2. Client-Linter: Regex-Warnung bei Mustern Telefon `\+?\d[\d\s/-]{6,}`, E-Mail `@`, IBAN `DE\d{2}`.
3. Serverseitiger Fallback-Redactor: ersetzt gefundene Muster durch `[REDACTED:phone]` etc., loggt `blueprint.notes.redacted`.
4. Placeholder-Text: „Nur betriebsbezogene Hinweise. Keine Namen, Telefonnummern, E-Mails."

## Rote Linien
- `owner_notes TEXT NOT NULL DEFAULT ''` auf Profil-Ebene: PII-Honeypot, zudem redundant → streichen.
- `current_tool` + `restaurant_name` zusammen bilden Geschäftsgeheimnis-Profil → Vertraulichkeitshinweis Pflicht.

## Risiken
- R1 (hoch): Freitextfelder akkumulieren PII.
- R2 (mittel): Fehlende Löschroute → faktisch unbegrenzte Speicherung.
- R3 (mittel): Report ohne Vertraulichkeitshinweis landet bei Dritten.
- R4 (niedrig): `access_log` wird selbst zum PII-Store, wenn `reason` unbedacht genutzt wird.

Vollständiger Dialog in agent-ID a68a47123d39c4d56.
