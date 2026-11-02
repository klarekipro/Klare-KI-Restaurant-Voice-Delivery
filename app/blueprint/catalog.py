"""Blueprint catalog: diagnostic areas and improvement modules.

All data in this module is **Richtwert / Diskussionsgrundlage** — no verified
integrations, no committed prices. Every budget is a span, every integration
starts `verified=False`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

CATALOG_VERSION = "2026-11-02.r2"

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
    preserved_systems: tuple[str, ...]       # Platzhalter — werden im Report
                                             # durch current_tool des Betriebs
                                             # ergänzt, nie durch MVP-Pfade.
    required_integrations: tuple[Integration, ...]
    possible_tools: tuple[Tool, ...]
    complexity: str                 # "low" | "medium" | "high"
    budget_eur_from: int
    budget_eur_to: int
    expected_effect: str            # trägt immer Label "zu validieren"
    requires_verification: tuple[str, ...]
    addresses_area_codes: tuple[str, ...]
    primary_area: str               # Haupt-Treiberbereich für current_tool-Lookup
    # Explizite Applicability-Signale (für Codex-nachvollziehbare Logik):
    requires_own_delivery: bool = False
    requires_own_phone_channel: bool = False
    requires_direct_online_channel: bool = False


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
        title="KI-gestützte Telefonannahme",
        problem=(
            "Anrufe gehen in Stoßzeiten verloren oder binden Personal, "
            "das gleichzeitig im Service oder in der Küche gebraucht wird."
        ),
        proposal=(
            "Wenn Anrufe tatsächlich verloren gehen oder die Telefonannahme "
            "durchgehend durch Personal gebunden ist, kann ein KI-Sprachassistent "
            "einen Teil der Anrufe strukturiert aufnehmen und als Bestell-Entwurf "
            "zur Freigabe durch eine Person übergeben. Reihenfolge der Prüfung: "
            "erstens Konfiguration oder Routing beim aktuellen Telefonanbieter, "
            "zweitens vertraglich zulässiger Zukauf eines Sprach-Dienstes, "
            "drittens eigene Entwicklung — nur wenn die ersten beiden nicht "
            "ausreichen."
        ),
        preserved_systems=(
            "Aktuelle Telefonnummer und Telefonanlage des Betriebs",
            "Aktueller Workflow der Freigabe durch eine Person",
        ),
        required_integrations=(
            Integration("Telefonanbieter / SIP-Trunk des Betriebs",
                        "Rufumleitung oder paralleles Routing — abhängig vom Anbieter"),
            Integration("Bestehende Bestellaufnahme (POS, CRM oder manueller Prozess)",
                        "Entwurf-Übergabe nur nach Freigabe durch eine Person"),
        ),
        possible_tools=(
            Tool("Newo (potenzieller Dritter)",
                 "Markt-Kandidat, keine E2E-Verifikation vorhanden",
                 third_party=True, verified=False),
            Tool("Alternative Sprach-Provider",
                 "Auswahl nach deutscher Sprach-Qualität, Datenschutz, Preis",
                 third_party=True, verified=False),
        ),
        complexity="medium",
        budget_eur_from=2500,
        budget_eur_to=9000,
        expected_effect=(
            "Hypothese: weniger verlorene Anrufe und Entlastung des Personals. "
            "Nur im konkreten Pilot zu validieren."
        ),
        requires_verification=(
            "Technische Machbarkeit der Rufumleitung beim aktuellen Telefonanbieter",
            "Datenschutz- und Hinweispflichten gegenüber Anrufenden (DSGVO + AI-Act Art. 50)",
            "Deutsche Spracherkennungs-Qualität im konkreten Dialekt-Umfeld",
            "Belastbare Eskalation an Personal bei nicht erkannter Bestellung",
        ),
        addresses_area_codes=("phone",),
        primary_area="phone",
        requires_own_phone_channel=True,
    ),
    Improvement(
        code="unified_order_intake",
        title="Vereinheitlichte Bestellannahme",
        problem=(
            "Bestellungen laufen über mehrere Kanäle (Telefon, Plattformen, eigene Seite) "
            "in getrennte Oberflächen; das Personal muss parallel mehrere Tablets bedienen."
        ),
        proposal=(
            "Ziel: eingehende Bestellungen in einer Oberfläche sichtbar machen. "
            "Ob Doppelerfassung tatsächlich entfällt, hängt von der POS-Schnittstelle, "
            "den Plattform-Freigaben und der Produktabdeckung des gewählten Middleware "
            "ab und ist pro Bridge separat zu prüfen. Reihenfolge: bestehendes POS-Modul "
            "des Betriebs → geprüftes Middleware (z. B. HubRise, Deliverect) für die "
            "konkrete POS/Plattform-Paarung → direkte APIs nur bei doppeltem Mehrwert."
        ),
        preserved_systems=(
            "Bestehende Verträge mit Lieferplattformen",
            "Aktuelle Freigabepraxis durch eine Person vor der Küche",
        ),
        required_integrations=(
            Integration("Lieferplattformen (Lieferando/Uber/Wolt)",
                        "Nur über vertraglich zugelassenen Weg; einige Kanäle liefern "
                        "Stornierungen nicht automatisch zurück"),
            Integration("POS des Betriebs",
                        "Übernahme freigegebener Bestellungen; API-Scopes und Version zu prüfen"),
        ),
        possible_tools=(
            Tool("Middleware (HubRise, Deliverect o. ä.)",
                 "Marktangebote, Eignung je POS/Plattform/Land zu prüfen",
                 third_party=True, verified=False),
            Tool("Direkte API je Plattform",
                 "Nur bei genehmigtem Partner-Zugang und wirtschaftlichem Volumen",
                 third_party=True, verified=False),
        ),
        complexity="high",
        budget_eur_from=4000,
        budget_eur_to=18000,
        expected_effect=(
            "Hypothese: weniger Tablet-Wechsel. Faktische Reduktion und mögliche "
            "Konflikte bei Stornos oder Deals abhängig vom konkreten Bridge."
        ),
        requires_verification=(
            "Vertragliche Zulässigkeit der API-Nutzung je Plattform",
            "Technische Schnittstellen des eingesetzten POS",
            "Abdeckung von Storno/Refund im gewählten Middleware",
            "Zuständigkeit für manuelle Nacharbeit nicht übertragener Statuswechsel",
        ),
        addresses_area_codes=("delivery_platforms", "online_orders", "pos"),
        primary_area="delivery_platforms",
    ),
    Improvement(
        code="kds",
        title="Küchenanzeige",
        problem=(
            "Bons werden gedruckt, gehen verloren oder sind in Stoßzeiten "
            "nicht mehr lesbar; Reihenfolge und Status sind unklar."
        ),
        proposal=(
            "Nur wenn eine Küchenanzeige fehlt oder die vorhandene unzureichend "
            "ist, kommt eine Lösung in Frage. Reihenfolge: Konfiguration oder "
            "Erweiterung des vorhandenen Kassen-/Küchensystems; wenn das nicht "
            "trägt, Markt-Produkt für Küchenanzeige; eine eigene Lösung nur "
            "nach dokumentiertem Pass und mit Rückfall auf Bon-Drucker."
        ),
        preserved_systems=(
            "Vorhandenes Kassen-/Küchensystem des Betriebs",
            "Bon-Drucker als Rückfallebene",
        ),
        required_integrations=(
            Integration("POS des Betriebs",
                        "Status-Rückmeldung nur wenn das vorhandene System es unterstützt"),
        ),
        possible_tools=(
            Tool("Konfiguration/Erweiterung des bestehenden Küchensystems",
                 "Erste Option — bevorzugt vor Neueinführung",
                 third_party=True, verified=False),
            Tool("Markt-Produkte für Küchenanzeige",
                 "Standardlösungen; Hardware-Eignung in der konkreten Küche zu prüfen",
                 third_party=True, verified=False),
        ),
        complexity="low",
        budget_eur_from=1500,
        budget_eur_to=5000,
        expected_effect=(
            "Hypothese: weniger verlorene Bons; messbare Zubereitungszeiten. "
            "Nur im konkreten Betrieb zu validieren."
        ),
        requires_verification=(
            "Hardware-Verfügbarkeit in der Küche (Bildschirm, Halterung, Spritzwasserschutz)",
            "Fähigkeit des bestehenden Kassensystems, Anzeige-Status zurückzuliefern",
        ),
        addresses_area_codes=("kitchen",),
        primary_area="kitchen",
    ),
    Improvement(
        code="delivery_mgmt",
        title="Fahrer- und Dispatch-Management",
        problem=(
            "Eigene Fahrer werden per Zuruf disponiert; der Live-Status einer "
            "laufenden Zustellung ist in der Zentrale nicht sichtbar."
        ),
        proposal=(
            "Nur relevant, wenn der Betrieb tatsächlich eigene Fahrer disponiert. "
            "Bei reiner Plattform-Lieferung (z. B. Lieferando-Fahrer) ist der "
            "Dispatch nicht beim Betrieb — dann entfällt dieses Modul. "
            "Wenn eigene Fahrer vorhanden sind und Live-Status fehlt: zuerst "
            "Konfigurations-Erweiterung des eingesetzten Dispatch-Tools, dann "
            "Standardprodukte am Markt, als letzte Option eigene Lösung."
        ),
        preserved_systems=(
            "Aktuelles Dispatch-Werkzeug des Betriebs",
            "Vorhandene mobile Endgeräte der Fahrer",
        ),
        required_integrations=(
            Integration("Kartenanbieter",
                        "Navigation; nur bei dokumentiertem Datenschutzkonzept"),
        ),
        possible_tools=(
            Tool("Konfiguration/Erweiterung des bestehenden Dispatch-Tools",
                 "Erste Option, wenn ein solches Werkzeug existiert",
                 third_party=True, verified=False),
            Tool("Standardprodukte für Fahrer-Disposition",
                 "Markt-Produkte; Datenschutz und mobile Verfügbarkeit zu prüfen",
                 third_party=True, verified=False),
        ),
        complexity="medium",
        budget_eur_from=2000,
        budget_eur_to=8000,
        expected_effect=(
            "Hypothese: schnellere Reaktion auf verspätete oder fehlgeschlagene "
            "Lieferungen. Nur im konkreten Betrieb zu validieren."
        ),
        requires_verification=(
            "Vorliegen eigener Zustellung (Pflicht)",
            "Datenschutzkonzept für optionale Positionsdaten der Fahrer",
            "Verfügbarkeit mobiler Endgeräte und ausreichender Mobilfunkabdeckung",
        ),
        addresses_area_codes=("couriers",),
        primary_area="couriers",
        requires_own_delivery=True,
    ),
    Improvement(
        code="crm_automation",
        title="Stammkunden- und Rückgewinnungs-Workflow",
        problem=(
            "Stammkunden werden nicht systematisch erfasst; Rückgewinnung ist Zufall."
        ),
        proposal=(
            "Wenn ein CRM fehlt oder nur manuell geführt wird, ist zu prüfen: "
            "nutzt das bestehende POS/Reservierungssystem bereits ein CRM-Modul? "
            "Erst wenn das nicht ausreicht, kommt eine Erweiterung oder ein "
            "Markt-CRM in Frage. Jede Aussendung nur mit dokumentiertem Opt-in. "
            "Bewertungsmanagement wird separat behandelt."
        ),
        preserved_systems=(
            "Bestehende Kundenerfassung im POS oder im Reservierungssystem",
            "Dokumentierte Opt-ins des Betriebs",
        ),
        required_integrations=(
            Integration("E-Mail-/SMS-Versand",
                        "Nur bei Opt-in; Dienstleister vertraglich zu prüfen"),
        ),
        possible_tools=(
            Tool("CRM-Modul des bestehenden POS/Reservierungssystems",
                 "Erste Option prüfen",
                 third_party=True, verified=False),
            Tool("Standard-CRM-Produkte am Markt",
                 "Markt-Produkte; DSGVO-Pass im konkreten Betrieb zu prüfen",
                 third_party=True, verified=False),
        ),
        complexity="medium",
        budget_eur_from=1800,
        budget_eur_to=7000,
        expected_effect=(
            "Hypothese: Reaktivierung inaktiver Kunden mit Opt-in. "
            "Wirkung nur mit Baseline messbar."
        ),
        requires_verification=(
            "DSGVO-Grundlage und Opt-in-Nachweis vor jedem Versand",
            "Datenqualität der bestehenden Kundenliste",
            "Zustellbarkeit der Kontaktdaten (bounced/invalid)",
        ),
        addresses_area_codes=("crm",),
        primary_area="crm",
    ),
    Improvement(
        code="owner_analytics",
        title="Betreiber-Analytik",
        problem=(
            "Es fehlt eine regelmäßige Übersicht über Bestellungen, Umsatz, "
            "Zubereitungs- und Lieferzeiten; Entscheidungen beruhen auf "
            "Erfahrung ohne tägliche Kennzahlen."
        ),
        proposal=(
            "Wenn keine Kennzahlen regelmäßig genutzt werden, zunächst prüfen, "
            "ob POS, Kassenbuch oder Plattform-Backend bereits ausreichend "
            "Berichte liefern. Erst wenn das nicht hinreicht, kommt ein "
            "einfacher Report-Zusammenzug in Frage. Kein Export in externe "
            "BI-Systeme als Standardannahme."
        ),
        preserved_systems=(
            "Berichte des bestehenden POS / Plattform-Backends",
            "Papier- oder Excel-Übersichten des Betriebs",
        ),
        required_integrations=(),
        possible_tools=(
            Tool("Nutzung vorhandener POS/Plattform-Berichte",
                 "Erste Option prüfen; viele POS bieten tägliche Reports",
                 third_party=True, verified=False),
            Tool("Einfacher interner Report-Zusammenzug",
                 "Erst wenn vorhandene Berichte nicht ausreichen",
                 third_party=False, verified=False),
        ),
        complexity="low",
        budget_eur_from=1200,
        budget_eur_to=4500,
        expected_effect=(
            "Hypothese: bessere Entscheidungsgrundlage. Nur mit vereinbartem "
            "Baseline-Vergleich messbar."
        ),
        requires_verification=(
            "Welche Kennzahlen die Inhaberin oder der Inhaber tatsächlich nutzt",
            "Verfügbarkeit vergleichbarer Zeiträume (Vorjahr, Saison)",
        ),
        addresses_area_codes=("analytics",),
        primary_area="analytics",
    ),
    Improvement(
        code="staff_automation",
        title="Automatisierung manueller Prozesse",
        problem=(
            "Zettel, Excel-Tabellen und Weitergabe per Zuruf verursachen "
            "Doppelerfassung und sind ausfallgefährdet."
        ),
        proposal=(
            "Nur konkret benannte und wiederholte manuelle Prozesse werden "
            "automatisiert. Als Erstes prüfen, ob das vorhandene POS, "
            "Schichtplan- oder Reservierungs-System die Aufgabe bereits "
            "abdeckt. Sonst kleine, prüfbare Hilfsmittel ohne Zwang zur "
            "Fremdsoftware."
        ),
        preserved_systems=(
            "Bestehende Rollen und Zuständigkeiten im Betrieb",
            "Vorhandene POS-/Schichtplan-Funktionen",
        ),
        required_integrations=(),
        possible_tools=(
            Tool("Vorhandene POS-/Schichtplan-Funktionen prüfen",
                 "Erste Option",
                 third_party=True, verified=False),
            Tool("Kleine interne Hilfsmittel (Formular, Checkliste)",
                 "Nur bei doppelter Erfassung mit messbarem Mehraufwand",
                 third_party=False, verified=False),
        ),
        complexity="low",
        budget_eur_from=800,
        budget_eur_to=4000,
        expected_effect=(
            "Hypothese: weniger Übergabe-Fehler bei Schichtwechsel. "
            "Nur mit vorher benanntem Prozess messbar."
        ),
        requires_verification=(
            "Konkret genannte Prozesse mit messbarem Zeitverlust",
            "Zustimmung der betroffenen Mitarbeitenden",
        ),
        addresses_area_codes=("manual_ops",),
        primary_area="manual_ops",
    ),
    Improvement(
        code="review_mgmt",
        title="Bewertungsmanagement",
        problem=(
            "Negative Bewertungen auf Google oder Lieferportalen bleiben "
            "unbeantwortet und senken die Sichtbarkeit."
        ),
        proposal=(
            "Nur relevant, wenn der Betrieb Bewertungen als konkrete Baustelle "
            "benennt. Monitoring von eingehenden Bewertungen mit "
            "Antwortvorschlägen zur Freigabe durch den Betrieb. Keine "
            "automatische Veröffentlichung."
        ),
        preserved_systems=(
            "Vorhandene Bewertungs-Accounts des Betriebs",
            "Aktueller Antwortprozess durch Inhaber oder Marketing",
        ),
        required_integrations=(
            Integration("Google Business Profile",
                        "Lesender Zugriff auf Bewertungen; Nutzungsbedingungen zu prüfen"),
            Integration("Lieferplattformen",
                        "Falls API-Zugriff auf Bewertungen vertraglich zugelassen"),
        ),
        possible_tools=(
            Tool("Monitoring-Dienste am Markt",
                 "Kompatibilität je Plattform zu prüfen",
                 third_party=True, verified=False),
        ),
        complexity="medium",
        budget_eur_from=1500,
        budget_eur_to=6000,
        expected_effect=(
            "Hypothese: höhere Antwortquote. Nur mit vorher gezählter Baseline messbar."
        ),
        requires_verification=(
            "API-Zugänge und Nutzungsbedingungen je Plattform",
            "Freigabeprozess im Betrieb (wer antwortet?)",
            "Reaktionszeit, die der Betrieb halten kann",
        ),
        addresses_area_codes=("crm",),
        primary_area="crm",
    ),
    Improvement(
        code="workflow_automation",
        title="Schnittstellen-Automatisierung",
        problem=(
            "Daten müssen regelmäßig zwischen Systemen hin- und herkopiert werden "
            "(z. B. Umsätze an Steuerberater, Allergene zwischen Haus und Plattformen)."
        ),
        proposal=(
            "Erst konkrete Medienbrüche benennen (welche Datei, welche Zielsoftware, "
            "welche Frequenz). Dann prüfen, ob der betreffende Hersteller einen "
            "Export anbietet, der schon reicht. Erst wenn nicht, einfache "
            "Schnittstellen bauen — mit klarer Prüfinstanz der Daten vor Übernahme."
        ),
        preserved_systems=(
            "Bestehende Buchhaltungs-Software des Steuerberaters",
            "Plattform-Konten und bestehende Export-Funktionen",
        ),
        required_integrations=(
            Integration("DATEV / Buchhaltungs-Zielsystem",
                        "Exportformat des Steuerberaters zu bestätigen"),
            Integration("Plattform-APIs",
                        "Nur wenn vertraglich zulässig und Scope dokumentiert"),
        ),
        possible_tools=(
            Tool("Vorhandene Exporte des eingesetzten POS/Kassenbuchs",
                 "Erste Option prüfen",
                 third_party=True, verified=False),
            Tool("Interne Export-Jobs oder n8n-Flows",
                 "Nur bei dokumentiertem Prozess und bestimmter Zielsystem-Schnittstelle",
                 third_party=False, verified=False),
        ),
        complexity="high",
        budget_eur_from=3000,
        budget_eur_to=12000,
        expected_effect=(
            "Hypothese: weniger Monatsende-Spitzen. Nur mit vorher gezählten "
            "Übertragungsminuten pro Woche messbar."
        ),
        requires_verification=(
            "Steuerberater akzeptiert konkret den Exportweg",
            "Rechtliche Zulässigkeit je Plattform-API",
            "Fehler-Erkennung vor Übernahme (sonst Datenchaos im Zielsystem)",
        ),
        addresses_area_codes=("accounting", "menu_compliance", "manual_ops"),
        primary_area="accounting",
    ),
)

IMPROVEMENT_BY_CODE: Mapping[str, Improvement] = {i.code: i for i in IMPROVEMENTS}


def improvements_touching(area_code: str) -> tuple[Improvement, ...]:
    return tuple(i for i in IMPROVEMENTS if area_code in i.addresses_area_codes)
