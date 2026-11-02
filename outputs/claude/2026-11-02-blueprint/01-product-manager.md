# Product Manager Review — Blueprint Design Draft

Durchgeführt: 2026-11-02, read-only, keine Codeänderung.

## 1. Katalog-Lücken (DE-Lieferrestaurant)
Fehlen aktuell:
- Zahlungs-/Kassenschnittstellen (SumUp, Zettle, girocard, Rechnung)
- TSE/Kassensicherungsverordnung & GoBD-Archivierung
- Lieferplattformen-Entkopplung (Lieferando/Uber/Wolt-Tablet-Chaos)
- Rechnungswesen/DATEV-Export
- Allergene/Zusatzstoffe nach LMIV
- Schichtplanung/Zeiterfassung (ArbZG, Mindestlohn-Doku)
- Telefon-Infrastruktur (SIP-Trunk, Rufnummern, Weiterleitung)

## 2. Pflichtfelder `diagnostic_profiles`
- Rechtsform & USt-ID / Rechnungsadresse
- Ansprechpartner + Rolle + direkte Telefon/E-Mail
- Standortanzahl / Filialstruktur
- Avg. Bestellwert und Delivery/Pickup-Anteil
- Peak-Hours und Anrufvolumen pro Tag
- Vertragsbindungen (Lieferando-Exklusivität, POS-Leasing)
- Budget-Indikation / Entscheidungszeitraum

## 3. Report-Pflichtbestandteile
- Ist-Zustand pro Bereich mit Status + Quelle
- Lücken-Liste mit Priorität + bezug zum Werkzeug
- Maßnahmen mit Umfang, Abhängigkeiten, zu bestätigenden Annahmen
- Preisrahmen als Spanne, getrennt Audit / Integration / Betrieb
- Next Steps mit Verantwortlichen, Zugängen, Zeithorizont

## 4. Rote Linien (Formulierungen)
- `time_loss_minutes_per_day`: Label „geschätzte manuelle Zeit pro Tag laut Betreiber (unbestätigt)", nie unkommentiert summieren.
- Budget-Range: „Richtwert Klare KI, nicht Angebot; verbindliche Preise nur nach Audit."
- „individueller Verbesserungsplan" → „Diskussionsgrundlage für Audit-Angebot".
- Modulbeschreibungen: „mögliche Wirkung — zu validieren", keine Minuten-/Umsatz-Versprechen.
- Priorität bei `missing`: „Priorität = Vorschlag, nicht Dringlichkeitsbewertung".

## 5. MVP-Priorität — entbehrlich
- Review-Management / Bewertungsportale
- Staff-Automation / Schichtplanung
- Owner-Analytics als separater Bereich (bereits durch Dashboard-Demo abgedeckt)

## Offen
- Vollständige Liste der 12 Bereiche?
- Zielkäufer: Owner-Operator oder Kette?
- Report rechtsverbindlich oder reine Gesprächsgrundlage?

Vollständiger Agentendialog in agent-ID a67129201b771b58c.
