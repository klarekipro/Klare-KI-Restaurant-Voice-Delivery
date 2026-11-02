"""Blueprint catalog: diagnostic areas and improvement modules.

All data in this module is **Richtwert / Diskussionsgrundlage** — no verified
integrations, no committed prices. Every budget is a span, every integration
starts `verified=False`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

CATALOG_VERSION = "2026-11-02"

STATUS_CODES = ("available", "partial", "manual", "missing", "unknown")
STATUS_DE: Mapping[str, str] = {
    "available": "Bereits vorhanden",
    "partial":   "Teilweise vorhanden",
    "manual":    "Manueller Prozess",
    "missing":   "Fehlt",
    "unknown":   "Noch zu klären",
}
STATUS_CHIP: Mapping[str, str] = {
    "available": "status-badge--available",
    "partial":   "status-badge--partial",
    "manual":    "status-badge--manual",
    "missing":   "status-badge--missing",
    "unknown":   "status-badge--unknown",
}

PRIORITY_DE: Mapping[str, str] = {
    "high":   "Hohe Priorität",
    "medium": "Mittlere Priorität",
    "low":    "Niedrige Priorität",
}


@dataclass(frozen=True)
class Area:
    code: str
    title: str
    short: str
    guiding_questions: tuple[str, ...]


@dataclass(frozen=True)
class Integration:
    name: str
    purpose: str
    verified: bool = False


@dataclass(frozen=True)
class Tool:
    name: str
    note: str
    third_party: bool = True
    verified: bool = False


@dataclass(frozen=True)
class Improvement:
    code: str
    title: str
    problem: str
    proposal: str
    preserved_systems: tuple[str, ...]
    required_integrations: tuple[Integration, ...]
    possible_tools: tuple[Tool, ...]
    complexity: str                 # "low" | "medium" | "high"
    budget_eur_from: int
    budget_eur_to: int
    expected_effect: str            # trägt immer Label "zu validieren"
    requires_verification: tuple[str, ...]
    addresses_area_codes: tuple[str, ...]


DIAGNOSE_AREAS: tuple[Area, ...] = (
    Area(
        code="pos",
        title="Kassen- und Bestellsystem",
        short="POS",
        guiding_questions=(
            "Welche Kassensoftware ist im Einsatz?",
            "Werden Bestellungen aus allen Kanälen in der Kasse zusammengeführt?",
            "Ist eine Schnittstelle zu Küchenanzeige/Bons vorhanden?",
        ),
    ),
    Area(
        code="payments",
        title="Zahlung, TSE und GoBD",
        short="Zahlung",
        guiding_questions=(
            "Welche Zahlungsarten werden akzeptiert (bar, Karte, Rechnung)?",
            "Ist die TSE (Technische Sicherungseinrichtung) angebunden und zertifiziert?",
            "Wie werden Belege nach GoBD archiviert?",
        ),
    ),
    Area(
        code="delivery_platforms",
        title="Lieferplattformen",
        short="Plattformen",
        guiding_questions=(
            "Welche Plattformen (Lieferando, Uber Eats, Wolt) sind aktiv?",
            "Gibt es einen Plattform-Aggregator oder laufen Tablets parallel?",
            "Werden Plattform-Bestellungen in die Küchenanzeige übernommen?",
        ),
    ),
    Area(
        code="phone",
        title="Telefonie und Anrufannahme",
        short="Telefon",
        guiding_questions=(
            "Wer nimmt Anrufe an, auch zu Stoßzeiten?",
            "Gehen Anrufe verloren? Wenn ja, geschätzt wie viele pro Tag?",
            "Gibt es eine Rufumleitung oder Mailbox-Abfrage?",
        ),
    ),
    Area(
        code="online_orders",
        title="Online-Bestellungen (eigene Kanäle)",
        short="Online",
        guiding_questions=(
            "Gibt es eine eigene Bestellseite oder App?",
            "Wie fließen Online-Bestellungen in Küche und Kasse?",
            "Werden Stammkunden digital wiedererkannt?",
        ),
    ),
    Area(
        code="kitchen",
        title="Küchenorganisation",
        short="Küche",
        guiding_questions=(
            "Werden Bestellungen auf Bons gedruckt oder auf Küchenbildschirm angezeigt?",
            "Welche Posten sind in Stoßzeiten der Flaschenhals?",
            "Werden Zubereitungszeiten gemessen?",
        ),
    ),
    Area(
        code="couriers",
        title="Fahrer und Dispatch",
        short="Lieferung",
        guiding_questions=(
            "Wie werden Fahrer disponiert?",
            "Nutzen Fahrer eine mobile Ansicht mit Navigation?",
            "Wird der Status der Zustellung an die Zentrale zurückgespiegelt?",
        ),
    ),
    Area(
        code="crm",
        title="Stammkunden und Rückgewinnung",
        short="CRM",
        guiding_questions=(
            "Werden Stammkunden mit Adresse und Historie geführt?",
            "Gibt es Kampagnen für inaktive Kunden?",
            "Welche DSGVO-Pflichten werden heute dokumentiert?",
        ),
    ),
    Area(
        code="analytics",
        title="Berichte und Kennzahlen",
        short="Analytik",
        guiding_questions=(
            "Welche Kennzahlen schaut sich die Inhaberin oder der Inhaber täglich an?",
            "Werden Zubereitungszeiten, Stornoquote, Lieferzeiten gemessen?",
            "Gibt es einen wöchentlichen Report?",
        ),
    ),
    Area(
        code="menu_compliance",
        title="Speisekarte und LMIV (Allergene)",
        short="Allergene",
        guiding_questions=(
            "Sind Allergene und Zusatzstoffe nach LMIV ausgewiesen?",
            "Wie wird die Speisekarte zwischen Haus, Website und Plattformen synchronisiert?",
            "Wer pflegt Preisänderungen?",
        ),
    ),
    Area(
        code="accounting",
        title="Buchhaltung und DATEV-Export",
        short="Buchhaltung",
        guiding_questions=(
            "Wie werden Umsätze an den Steuerberater übergeben (manuell, DATEV-Export)?",
            "Welche Belege liegen digital, welche in Papier?",
            "Gibt es Medienbrüche zwischen Kasse und Buchhaltung?",
        ),
    ),
    Area(
        code="manual_ops",
        title="Manuelle Betriebsprozesse",
        short="Manuell",
        guiding_questions=(
            "Welche Tätigkeiten werden heute per Zettel, Excel oder im Kopf gemacht?",
            "Wo entsteht täglich Zeitverlust durch Doppelerfassung?",
            "Welche Prozesse hängen an einer bestimmten Person?",
        ),
    ),
)

AREA_BY_CODE: Mapping[str, Area] = {a.code: a for a in DIAGNOSE_AREAS}


IMPROVEMENTS: tuple[Improvement, ...] = (
    Improvement(
        code="ai_phone_reception",
        title="KI-Telefonannahme",
        problem=(
            "Anrufe gehen in Stoßzeiten verloren oder binden Personal, "
            "das gleichzeitig im Service oder in der Küche gebraucht wird."
        ),
        proposal=(
            "Ein KI-Sprachassistent nimmt Anrufe an, erfasst Bestellungen in Deutsch "
            "und übergibt sie an die bestehende Konfirmierer-Oberfläche zur Freigabe. "
            "Die bestehende Telefonnummer bleibt erhalten, die Rufumleitung wird "
            "nur bei Belegt- oder Nichtannahme aktiv."
        ),
        preserved_systems=(
            "Bestehende Telefonnummer und -anlage",
            "Konfirmierer-Oberfläche",
            "Küchenanzeige",
        ),
        required_integrations=(
            Integration("SIP/Telefonanbieter", "Rufumleitung zur KI-Nummer"),
            Integration("Konfirmierer-Queue", "Übergabe als neue Bestellung"),
        ),
        possible_tools=(
            Tool("Newo", "Potenzieller Drittanbieter für Sprach-KI", third_party=True, verified=False),
            Tool("Alternative Sprach-Provider", "Austauschbar; eigene Prüfung nötig",
                 third_party=True, verified=False),
        ),
        complexity="medium",
        budget_eur_from=2500,
        budget_eur_to=9000,
        expected_effect=(
            "Weniger verlorene Anrufe in Stoßzeiten; "
            "die Küche wird vom Telefon entlastet (zu validieren im Pilot)."
        ),
        requires_verification=(
            "Technische Machbarkeit der Rufumleitung beim aktuellen Telefonanbieter",
            "Datenschutz- und Hinweispflichten gegenüber Anrufenden",
            "Qualität der deutschen Spracherkennung im konkreten Dialekt-Umfeld",
        ),
        addresses_area_codes=("phone", "manual_ops"),
    ),
    Improvement(
        code="unified_order_intake",
        title="Vereinheitlichte Bestellannahme",
        problem=(
            "Bestellungen laufen über mehrere Kanäle (Telefon, Plattformen, eigene Seite) "
            "in getrennte Oberflächen; das Personal muss parallel mehrere Tablets bedienen."
        ),
        proposal=(
            "Alle Kanäle münden in eine Oberfläche zur Freigabe durch die Konfirmierenden. "
            "Doppelerfassung in der Kasse entfällt, Plattform-Bestellungen werden angenommen "
            "oder abgelehnt im selben Workflow wie Telefonbestellungen."
        ),
        preserved_systems=(
            "Konfirmierer-Oberfläche",
            "Vorhandene Verträge mit Plattformen",
        ),
        required_integrations=(
            Integration("Lieferando/Uber/Wolt", "Lesender Zugriff auf eingehende Bestellungen"),
            Integration("POS", "Übergabe akzeptierter Bestellungen"),
        ),
        possible_tools=(
            Tool("Plattform-Aggregator (Deliverect o. ä.)",
                 "Marktangebot, Kompatibilität je POS zu prüfen",
                 third_party=True, verified=False),
            Tool("Direkte API je Plattform",
                 "Nur bei größeren Betrieben wirtschaftlich", third_party=True, verified=False),
        ),
        complexity="high",
        budget_eur_from=4000,
        budget_eur_to=18000,
        expected_effect=(
            "Weniger Tablet-Chaos, konsistente Küchenbons (zu validieren)."
        ),
        requires_verification=(
            "Vertragliche Zulässigkeit der API-Nutzung bei allen genutzten Plattformen",
            "Technische Schnittstellen des bestehenden POS",
            "Durchsatz der Konfirmierer-Oberfläche bei Peak",
        ),
        addresses_area_codes=("delivery_platforms", "online_orders", "pos"),
    ),
    Improvement(
        code="kds",
        title="Küchenanzeige (KDS)",
        problem=(
            "Bons werden gedruckt, gehen verloren oder sind in Stoßzeiten "
            "nicht mehr lesbar; Reihenfolge und Status sind unklar."
        ),
        proposal=(
            "Eine Küchenanzeige mit großen Touch-Targets zeigt Bestellungen, "
            "deren Status, Zubereitungszeiten und erlaubt das Markieren als „fertig“. "
            "Die bestehende Küche-Oberfläche aus dem MVP ist Ausgangspunkt."
        ),
        preserved_systems=(
            "Vorhandene Küche-Oberfläche (/kitchen)",
            "Bon-Drucker als Rückfallebene",
        ),
        required_integrations=(
            Integration("POS", "Status-Rückmeldung an Kasse (optional)"),
        ),
        possible_tools=(
            Tool("Erweiterung der MVP-Küche-Oberfläche",
                 "Eigenentwicklung, bevorzugt vor externem KDS", third_party=False),
        ),
        complexity="low",
        budget_eur_from=1500,
        budget_eur_to=5000,
        expected_effect=(
            "Keine verlorenen Bons; messbare Zubereitungszeiten (zu validieren)."
        ),
        requires_verification=(
            "Hardware-Verfügbarkeit in der Küche (Bildschirm, Halterung, Spritzwasserschutz)",
        ),
        addresses_area_codes=("kitchen",),
    ),
    Improvement(
        code="delivery_mgmt",
        title="Fahrer- und Dispatch-Management",
        problem=(
            "Fahrerzuweisung erfolgt per Zuruf; der Status einer laufenden Zustellung "
            "ist in der Zentrale nicht sichtbar."
        ),
        proposal=(
            "Die bestehende Fahrer- und Dispatch-Oberfläche wird um Live-Status, "
            "Navigation und optionale Positionsübermittlung erweitert. Der Betrieb "
            "sieht in Echtzeit, wer wo ist."
        ),
        preserved_systems=(
            "Vorhandene Dispatch- und Fahrer-Oberfläche",
        ),
        required_integrations=(
            Integration("Kartenanbieter (Google Maps o. ä.)", "Navigation"),
        ),
        possible_tools=(
            Tool("Erweiterung der MVP-Fahrer-Oberfläche",
                 "Progressive Web App, keine neue App im Store nötig", third_party=False),
        ),
        complexity="medium",
        budget_eur_from=2000,
        budget_eur_to=8000,
        expected_effect=(
            "Schnellere Reaktion auf verspätete Lieferungen (zu validieren)."
        ),
        requires_verification=(
            "Datenschutzkonzept für optionale Positionsdaten der Fahrer",
            "Verfügbarkeit mobiler Endgeräte",
        ),
        addresses_area_codes=("couriers",),
    ),
    Improvement(
        code="crm_automation",
        title="CRM-Automatisierung",
        problem=(
            "Stammkunden werden nicht systematisch erfasst, Rückgewinnung ist Zufall."
        ),
        proposal=(
            "Die bestehende Kunden-Oberfläche wird um automatische Markierung "
            "wiederkehrender Nummern, Opt-out-Verwaltung und zeitgesteuerte "
            "Erinnerungen erweitert. Alle Mailings nur mit dokumentiertem Opt-in."
        ),
        preserved_systems=(
            "Vorhandene Kunden-Oberfläche (/customers)",
        ),
        required_integrations=(
            Integration("E-Mail-Versand (SMTP oder Dienstleister)",
                        "Nur bei Opt-in; nicht Teil des MVP"),
        ),
        possible_tools=(
            Tool("Erweiterung der MVP-Kunden-Oberfläche",
                 "Vor externem CRM bevorzugen", third_party=False),
        ),
        complexity="medium",
        budget_eur_from=1800,
        budget_eur_to=7000,
        expected_effect=(
            "Reaktivierung inaktiver Kunden (nur mit Opt-in; Wirkung zu validieren)."
        ),
        requires_verification=(
            "DSGVO-Grundlage und Opt-in-Nachweis vor jedem Versand",
            "Datenqualität der bestehenden Kundenliste",
        ),
        addresses_area_codes=("crm",),
    ),
    Improvement(
        code="owner_analytics",
        title="Betreiber-Analytik",
        problem=(
            "Es fehlt eine tägliche Übersicht über Bestellungen, Umsatz, "
            "Zubereitungs- und Lieferzeiten; Entscheidungen beruhen auf "
            "Erfahrung ohne tägliche Kennzahlen."
        ),
        proposal=(
            "Das bestehende Dashboard wird um Trendlinien, Vergleich zu Vortagen "
            "und Küchen-Kennzahlen erweitert. Kein Export in externe BI-Systeme."
        ),
        preserved_systems=(
            "Vorhandenes Dashboard (/dashboard)",
        ),
        required_integrations=(),
        possible_tools=(
            Tool("Erweiterung des MVP-Dashboards",
                 "Keine externen BI-Dienste nötig", third_party=False),
        ),
        complexity="low",
        budget_eur_from=1200,
        budget_eur_to=4500,
        expected_effect=(
            "Entscheidungsgrundlage für Personal- und Angebotssteuerung (zu validieren)."
        ),
        requires_verification=(
            "Welche Kennzahlen die Inhaberin oder der Inhaber tatsächlich nutzt",
        ),
        addresses_area_codes=("analytics",),
    ),
    Improvement(
        code="staff_automation",
        title="Automatisierung manueller Prozesse",
        problem=(
            "Zettel, Excel-Tabellen und Weitergabe per Zuruf verursachen "
            "Doppelerfassung und sind ausfallgefährdet."
        ),
        proposal=(
            "Identifizierte manuelle Prozesse werden als kleine, prüfbare "
            "Automatisierungen umgesetzt (z. B. Schichtübergabe, Vorbestellungen, "
            "Kassenabschluss-Checkliste)."
        ),
        preserved_systems=(
            "Bestehende Rollen und Zuständigkeiten",
        ),
        required_integrations=(),
        possible_tools=(
            Tool("Kleine interne Web-Formulare",
                 "Keine Fremdsoftware zwingend", third_party=False),
        ),
        complexity="low",
        budget_eur_from=800,
        budget_eur_to=4000,
        expected_effect=(
            "Weniger Übergabe-Fehler bei Schichtwechsel (zu validieren)."
        ),
        requires_verification=(
            "Priorisierung der konkreten Prozesse mit dem Betrieb",
        ),
        addresses_area_codes=("manual_ops",),
    ),
    Improvement(
        code="review_mgmt",
        title="Bewertungsmanagement",
        problem=(
            "Negative Bewertungen auf Google oder Lieferportalen bleiben "
            "unbeantwortet und senken die Sichtbarkeit."
        ),
        proposal=(
            "Monitoring von eingehenden Bewertungen mit Antwortvorschlägen "
            "zur Freigabe durch den Betrieb. Keine automatische Veröffentlichung."
        ),
        preserved_systems=(
            "Vorhandene Bewertungs-Accounts",
        ),
        required_integrations=(
            Integration("Google Business Profile", "Lesender Zugriff auf Bewertungen"),
            Integration("Lieferplattformen", "Falls API-Zugriff auf Bewertungen verfügbar"),
        ),
        possible_tools=(
            Tool("Monitoring-Service", "Marktangebote variieren, Kompatibilität zu prüfen",
                 third_party=True, verified=False),
        ),
        complexity="medium",
        budget_eur_from=1500,
        budget_eur_to=6000,
        expected_effect=(
            "Höhere Antwortquote auf Bewertungen (zu validieren)."
        ),
        requires_verification=(
            "API-Zugänge und Nutzungsbedingungen je Plattform",
            "Freigabeprozess im Betrieb (wer antwortet?)",
        ),
        addresses_area_codes=("crm",),
    ),
    Improvement(
        code="workflow_automation",
        title="Workflow-Automatisierung (Schnittstellen)",
        problem=(
            "Daten müssen täglich zwischen Systemen hin- und herkopiert werden "
            "(z. B. Umsätze an Steuerberater, Allergene zwischen Haus und Plattformen)."
        ),
        proposal=(
            "Gezielte Schnittstellen für die 2–3 häufigsten manuellen Übertragungen, "
            "z. B. automatischer DATEV-Export, Synchronisation der Speisekarte."
        ),
        preserved_systems=(
            "Bestehende Buchhaltungs-Software des Steuerberaters",
            "Plattform-Konten",
        ),
        required_integrations=(
            Integration("DATEV", "Exportformat, kein Online-Zugriff auf Mandantendaten"),
            Integration("Plattform-APIs", "Nur wenn vertraglich zulässig"),
        ),
        possible_tools=(
            Tool("Interne Export-Jobs",
                 "Keine Cloud-Pflicht, kann lokal laufen", third_party=False),
        ),
        complexity="high",
        budget_eur_from=3000,
        budget_eur_to=12000,
        expected_effect=(
            "Weniger Doppelerfassung, weniger Monatsende-Spitzen (zu validieren)."
        ),
        requires_verification=(
            "Steuerberater akzeptiert konkret den Exportweg",
            "Rechtliche Zulässigkeit je Plattform-API",
        ),
        addresses_area_codes=("accounting", "menu_compliance", "manual_ops"),
    ),
)

IMPROVEMENT_BY_CODE: Mapping[str, Improvement] = {i.code: i for i in IMPROVEMENTS}


def improvements_touching(area_code: str) -> tuple[Improvement, ...]:
    return tuple(i for i in IMPROVEMENTS if area_code in i.addresses_area_codes)
