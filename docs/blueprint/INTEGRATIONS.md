# Integrationen — bestätigt vs. unbestätigt

Stand: 2026-11-02 (Katalog-Version `2026-11-02`).

Blueprint macht keine technischen Zusagen über die Kompatibilität mit Drittanbietern.
Jede der folgenden Integrationen ist derzeit **nicht verifiziert**.
Bestätigungen können nur durch gezielte technische Prüfungen gegen die konkrete
Konfiguration eines Betriebs ergehen und müssen jeweils dokumentiert werden.

## Status aller im Katalog genannten Integrationen und Werkzeuge

| Verbesserung | Komponente | Typ | Status |
|---|---|---|---|
| KI-Telefonannahme | SIP/Telefonanbieter (Rufumleitung) | Integration | unbestätigt |
| KI-Telefonannahme | Konfirmierer-Queue (interne Übergabe) | Integration | unbestätigt |
| KI-Telefonannahme | Newo | Drittanbieter-Werkzeug | unbestätigt |
| KI-Telefonannahme | Alternative Sprach-Provider | Drittanbieter-Werkzeug | unbestätigt |
| Vereinheitlichte Bestellannahme | Lieferando / Uber / Wolt | Integration | unbestätigt |
| Vereinheitlichte Bestellannahme | POS (Allgemein) | Integration | unbestätigt |
| Vereinheitlichte Bestellannahme | Deliverect o. ä. | Drittanbieter-Werkzeug | unbestätigt |
| Vereinheitlichte Bestellannahme | Direkte Plattform-APIs | Drittanbieter-Werkzeug | unbestätigt |
| Küchenanzeige (KDS) | POS (Status-Rückmeldung) | Integration | unbestätigt |
| Küchenanzeige (KDS) | Erweiterung MVP-Küche-Oberfläche | Eigenentwicklung | nicht umgesetzt (geplant) |
| Fahrer- und Dispatch-Management | Kartenanbieter (z. B. Google Maps) | Integration | unbestätigt |
| CRM-Automatisierung | E-Mail-Versand (SMTP oder Dienstleister) | Integration | unbestätigt |
| Bewertungsmanagement | Google Business Profile | Integration | unbestätigt |
| Bewertungsmanagement | Lieferplattformen (API) | Integration | unbestätigt |
| Workflow-Automatisierung | DATEV-Exportformat | Integration | unbestätigt |
| Workflow-Automatisierung | Plattform-APIs | Integration | unbestätigt |

## Was „bestätigt" bedeutet (und was nicht)

- „Bestätigt" setzt voraus: eine konkrete technische Prüfung gegen die reale
  Konfiguration des Betriebs liegt vor; sie ist mit Datum, Prüfer und Methode
  dokumentiert; sie wurde unabhängig gegengeprüft.
- Marketing-Material oder öffentliche API-Dokumente Dritter reichen **nicht**
  als Bestätigung.

## Verifizierte Behauptungen im Blueprint selbst

- Die bestehenden MVP-Oberflächen (Konfirmierer, Küche, Dispatch, Fahrer,
  Dashboard, Kunden, Menü) laufen lokal und sind durch die Regressionstests
  des Repositories abgedeckt (`tests/test_e2e_flow.py`,
  `tests/test_demo_release.py`, `tests/test_hardening.py`).
- Blueprint-Routen (Diagnose anlegen, Bereich upserten, Vorschlag auswählen,
  Report rendern) sind durch `tests/test_blueprint.py` abgedeckt.
- Die Freitext-Redaction entfernt in Unit- und Integrationstests
  Telefonnummern (≥ 7 Ziffern), E-Mail- und IBAN-Muster.

## Explizit nicht verifiziert

- Druckausgabe des Reports in konkreten Browsern (Chrome, Safari, Firefox) —
  nur HTTP-Antwort und HTML-Struktur sind getestet, keine visuelle Prüfung.
- DSGVO-Compliance in konkreter Nutzung — qualifizierte Rechtsprüfung steht
  aus (siehe Privacy-Review).
- Barrierefreiheit nach WCAG — keine automatisierte Prüfung, nur strukturelle
  Vorgaben in der Vorlage.
