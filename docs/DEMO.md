# Demo-Skript — Klare KI Restaurant (lokal)

> Vollständiges Vorführskript auf Deutsch für die Mission-10 Demo-Release.
> Alle Schritte laufen gegen die lokale FastAPI-Anwendung ohne externe Dienste.

## 1. Vorbereitung

```bash
cd /pfad/zu/restaurant-demo-release
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# optional: frische Datenbank
rm -f data/mvp.sqlite*
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Browser öffnen: <http://127.0.0.1:8000/>

Die Demo nutzt vier Rollen (Zugangsdaten aus `README.md`):
`owner` / `confirmer` / `kitchen` / `courier1`.

Für den vollen Rundgang bitte **vier Browser-Tabs** oder **vier Browser-Profile** öffnen — ein Tab pro Rolle.

## 2. Rundgang (circa 7 Minuten)

### Schritt 1 — Erstanruf (Konfirmiererin)

- Tab 1: als `confirmer` anmelden → **Anruf**.
- Telefonnummer `+49 171 1234567` eingeben → **CRM-Abgleich**.
- Antwort: *Erstanruf — Daten bitte vollständig aufnehmen*.
- Name `Anna Neukunde`, Adresse `Berliner Str. 7, 10115 Berlin`, Notiz `3. Stock`.
- Positionen: `Pizza Margherita × 1`, `Cola 0,33L × 1`.
- Button **Bestellung an Konfirmiererin senden**.
- Erwartete Antwort: *Bestellung #1 erstellt (CRM: unmatched, Call sim-…)*.

### Schritt 2 — Stammkunden-Erkennung

- Nummer `+49 30 1234567` eingeben → **CRM-Abgleich**.
- Antwort: *Stammkunde* — Adresse wird vorbefüllt.
- Pizza Salami × 1 → absenden.
- CRM-Status: `matched`.

### Schritt 3 — Prüfung durch Konfirmiererin

- Zurück zur Queue: zwei Einträge mit **Neu – zu prüfen** (gelb).
- Bestellung #1 öffnen → eine Position hinzufügen (`Tiramisu × 1`) oder
  Menge einer Position ändern.
- **Bestätigen & an Küche senden** klicken.
- Flash-Banner: *Bestellung bestätigt und an die Küche übergeben*.
- Status in Queue wechselt zu **Bestätigt** (blau).

### Schritt 4 — Küche (Tab 2 als `kitchen`)

- Seite **Küche** zeigt die bestätigte Bestellung mit großen Positionskarten.
- **Start** → Status **In Zubereitung** (indigo).
- **Fertig** → Status **Fertig** (grün).
- Hinweis: Doppelklick auf **Fertig** ist idempotent (keine Fehlerseite).

### Schritt 5 — Dispatch (Tab 1, Konfirmiererin)

- Menüpunkt **Dispatch** → die fertige Bestellung ist gelistet.
- Fahrer aus Dropdown wählen (z. B. `Carlo Courier`) → **Zuweisen**.
- Flash-Banner: *Fahrer zugewiesen.*

### Schritt 6 — Fahrer-App (Tab 3 als `courier1`, idealerweise im
Mobile-Simulator des Browsers)

- Startseite **Meine Aufträge** zeigt die neue Lieferung.
- Auftragskarte antippen → Lieferungs-Screen.
- Große Primär-Taste **Navigator öffnen** öffnet Google Maps mit der Adresse.
- Taste **Anrufen** → Rufnummer wird eingeblendet, Zugriff landet im
  `access_log` (Audit).
- **Unterwegs** → Status **Unterwegs** (orange).
- **Zugestellt** → Status **Zugestellt** (grün).

### Schritt 7 — Dashboard (Tab 4 als `owner`)

- **Dashboard** zeigt:
  - KPI *Bestellungen* mit KI-Anteil.
  - Tabelle *Zugestellt pro Fahrerin/Fahrer* mit Umsatz.
  - KPI *Umsatz zugestellt* (nur erfolgreiche Lieferungen) und *aktiv (ohne
    Abbrüche)*.
  - Block **Küchenleistung**: *Zubereitete Bestellungen*, *Ø
    Zubereitungszeit* in Minuten, *Zubereitete Positionen*.
- Zeitraum-Umschaltung: **Heute** / **7 Tage**.

## 3. Fehler-Szenarien zum Vorzeigen

| Szenario                                   | Erwartete Reaktion                                     |
|--------------------------------------------|--------------------------------------------------------|
| Küche löst **Fertig** zweimal aus          | zweite Aktion ist still (keine Fehlerseite)            |
| Fahrer markiert **Zugestellt** zweimal     | zweite Aktion ist still                                |
| Konfirmiererin genehmigt leere Bestellung  | 400-Fehlerseite auf Deutsch                            |
| Nicht angemeldeter Zugriff auf `/kitchen`  | Weiterleitung zu `/login`                              |
| Kitchen öffnet `/customers`                | Fehlerseite **Kein Zugriff**                           |
| Ungültige PLZ (4 Ziffern) im Anruf-Formular| 400 + Hinweis *PLZ muss aus 5 Ziffern bestehen.*       |
| Doppelte `Idempotency-Key`-Nutzung         | gleiche Antwort wie erster Call                        |
| Idempotency-Key mit anderem Payload        | 409 + Hinweis auf Konflikt                             |

## 4. Persistenz-Prüfung

- Uvicorn stoppen (Ctrl+C).
- Neu starten.
- `/confirmer` zeigt die Bestellhistorie unverändert — SQLite-Datei bleibt
  bestehen unter `data/mvp.sqlite`.

## 5. Rollen-Zusammenfassung für die Vorführung

| Rolle      | Startseite      | Darf                                                    | Darf nicht                      |
|------------|-----------------|---------------------------------------------------------|---------------------------------|
| owner      | `/dashboard`    | alles lesen; Menü/Kunden bearbeiten                     | —                               |
| confirmer  | `/confirmer`    | Anruf, Prüfung, Dispatch, Kundenpflege                  | Dashboard, Menü-Preise ändern   |
| kitchen    | `/kitchen`      | Küchen-Queue bearbeiten                                 | Kundendaten einsehen            |
| courier    | `/courier`      | eigene Lieferungen bearbeiten; Phone-Reveal mit Audit   | fremde Lieferungen öffnen       |

## 6. Nicht Teil der Demo

- Echter SIP/ASR/LLM/TTS-Stack (nur Simulator) — siehe README §Voice-Integration.
- Externe Zahlungserfassung.
- Routen-Optimierung oder Delivery-Zone-Prüfung.
- OIDC/SSO oder Mehrmandantenfähigkeit.
