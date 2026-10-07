"""Regelbasierte Klassifizierung ohne KI – schnell, offline, kostenlos. Dient auch als Fallback."""

from __future__ import annotations

import re
from datetime import date

from ..extract import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from ..models import Classification
from .base import AIProvider, FileContext

# (Kategorie, Dokumenttyp, Schlüsselwörter, Tags) – Reihenfolge = Priorität
KEYWORD_RULES: list[tuple[str, str, list[str], list[str]]] = [
    ("Steuern", "Steuerbescheid", ["steuerbescheid", "finanzamt", "einkommensteuer", "lohnsteuerbescheinigung",
                                    "steuer-id", "steuernummer", "elster", "tax return"], ["steuern"]),
    ("Finanzen/Gehaltsabrechnungen", "Gehaltsabrechnung", ["gehaltsabrechnung", "lohnabrechnung", "entgeltabrechnung",
                                                            "payslip", "brutto/netto"], ["gehalt", "finanzen"]),
    ("Finanzen/Kontoauszüge", "Kontoauszug", ["kontoauszug", "account statement", "kontostand", "saldo alt"],
     ["bank", "finanzen"]),
    ("Finanzen/Rechnungen", "Rechnung", ["rechnung", "rechnungsnummer", "invoice", "rechnungsbetrag",
                                         "zahlbar bis", "ust-idnr", "mwst", "amount due"], ["rechnung", "finanzen"]),
    ("Finanzen/Quittungen", "Quittung", ["quittung", "kassenbon", "receipt", "beleg-nr"], ["quittung", "finanzen"]),
    ("Versicherungen", "Versicherung", ["versicherungsschein", "police", "versicherungsnummer", "beitragsrechnung",
                                        "insurance policy"], ["versicherung"]),
    ("Verträge", "Vertrag", ["vertrag", "vereinbarung", "kündigung", "laufzeit", "vertragsnummer", "agreement",
                             "contract", "unterschrift"], ["vertrag"]),
    ("Gesundheit", "Arztbrief", ["arztbrief", "befund", "diagnose", "krankenkasse", "rezept", "praxis dr",
                                 "arbeitsunfähigkeit"], ["gesundheit"]),
    ("Behörden", "Behördenschreiben", ["bürgeramt", "landratsamt", "aktenzeichen", "bescheid", "behörde",
                                       "meldebescheinigung"], ["behörde"]),
    ("Wohnen", "Wohnungsunterlage", ["mietvertrag", "nebenkostenabrechnung", "vermieter", "hausverwaltung",
                                     "stromabrechnung", "abschlag"], ["wohnen"]),
    ("Arbeit/Bewerbungen", "Bewerbung", ["bewerbung", "lebenslauf", "curriculum vitae", "anschreiben"], ["arbeit"]),
    ("Arbeit/Zeugnisse", "Zeugnis", ["arbeitszeugnis", "zeugnis", "zertifikat", "certificate"], ["zeugnis"]),
    ("Reisen", "Reiseunterlage", ["boarding pass", "buchungsbestätigung", "flug", "hotel", "reservierung",
                                  "bahncard", "ticket"], ["reise"]),
    ("Handbücher", "Handbuch", ["bedienungsanleitung", "user manual", "handbuch", "installation guide"], ["handbuch"]),
]

EXTENSION_CATEGORIES: dict[str, tuple[str, str]] = {
    **{e: ("Bilder", "Bild") for e in IMAGE_EXTENSIONS},
    **{e: ("Videos", "Video") for e in VIDEO_EXTENSIONS},
    **{e: ("Musik", "Audio") for e in [".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"]},
    **{e: ("Archive", "Archiv") for e in [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz"]},
    **{e: ("Installer", "Installer") for e in [".dmg", ".exe", ".msi", ".pkg", ".deb", ".rpm", ".appimage", ".msix"]},
    **{e: ("Tabellen", "Tabelle") for e in [".xlsx", ".xls", ".ods", ".csv", ".numbers"]},
    **{e: ("Präsentationen", "Präsentation") for e in [".pptx", ".ppt", ".odp", ".key"]},
    **{e: ("Code", "Code") for e in [".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs", ".sh", ".ipynb"]},
    **{e: ("Dokumente", "Dokument") for e in [".pdf", ".docx", ".doc", ".odt", ".txt", ".md", ".rtf", ".pages"]},
    **{e: ("Sonstiges/Kalender", "Kalendereintrag") for e in [".ics"]},
    **{e: ("Sonstiges/Schriftarten", "Schriftart") for e in [".ttf", ".otf", ".woff", ".woff2"]},
}

KNOWN_VENDORS = [
    "Telekom", "Vodafone", "O2", "1&1", "Amazon", "PayPal", "Apple", "Google", "Microsoft", "IKEA", "Otto",
    "Zalando", "Deutsche Bahn", "Lufthansa", "Allianz", "HUK-Coburg", "AOK", "TK", "Barmer", "DAK", "Sparkasse",
    "Commerzbank", "Deutsche Bank", "ING", "DKB", "N26", "Comdirect", "Vattenfall", "E.ON", "EnBW", "Stadtwerke",
    "ADAC", "Netflix", "Spotify", "Finanzamt", "MediaMarkt", "Saturn", "Lidl", "Aldi", "Rewe", "Edeka", "dm",
    "Rossmann", "Check24", "Booking.com", "Airbnb", "Uber", "Congstar", "Unitymedia", "Sky", "GEZ", "Rundfunkbeitrag",
]

_DATE_PATTERNS = [
    (re.compile(r"(?<!\d)(20\d{2}|19\d{2})[-_.](\d{1,2})[-_.](\d{1,2})(?!\d)"), "ymd"),
    (re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(20\d{2}|19\d{2})(?!\d)"), "dmy"),
    (re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})/(20\d{2})(?!\d)"), "dmy"),
    (re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)"), "ymd"),
]

_MONTHS = {"januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6, "juli": 7,
           "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12}
_DATE_WORDS = re.compile(r"\b(\d{1,2})\.\s*(" + "|".join(_MONTHS) + r")\s+(20\d{2})\b", re.IGNORECASE)

_AMOUNT_HINT = re.compile(
    r"(gesamtbetrag|rechnungsbetrag|endbetrag|gesamtsumme|zu zahlen|summe|total|betrag)[^\d]{0,30}"
    r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})|\d+(?:[.,]\d{2}))\s*(€|eur|euro|\$|usd)?",
    re.IGNORECASE,
)
_AMOUNT_ANY = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})\s*(€|eur|euro)", re.IGNORECASE)


def find_date(*texts: str) -> str | None:
    for text in texts:
        if not text:
            continue
        m = _DATE_WORDS.search(text)
        candidates: list[tuple[int, int, int]] = []
        if m:
            candidates.append((int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1))))
        for pattern, order in _DATE_PATTERNS:
            for match in pattern.finditer(text):
                a, b, c = (int(g) for g in match.groups())
                candidates.append((a, b, c) if order == "ymd" else (c, b, a))
        for y, mo, d in candidates:
            try:
                parsed = date(y, mo, d)
            except ValueError:
                continue
            if 1990 <= parsed.year <= date.today().year + 1:
                return parsed.isoformat()
    return None


def _parse_number(raw: str) -> float | None:
    raw = raw.replace(" ", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def find_amount(text: str) -> tuple[float | None, str | None]:
    m = _AMOUNT_HINT.search(text)
    if m:
        value = _parse_number(m.group(2))
        cur = (m.group(3) or "€").lower()
        return value, "USD" if cur in {"$", "usd"} else "EUR"
    amounts = [_parse_number(a.group(1)) for a in _AMOUNT_ANY.finditer(text)]
    amounts = [a for a in amounts if a is not None]
    if amounts:
        return max(amounts), "EUR"
    return None, None


def find_vendor(text: str, filename: str) -> str | None:
    haystack = f"{filename} {text[:3000]}".lower()
    for vendor in KNOWN_VENDORS:
        if re.search(r"(?<![a-z])" + re.escape(vendor.lower()) + r"(?![a-z])", haystack):
            return vendor
    return None


class HeuristicProvider(AIProvider):
    name = "heuristic"

    def classify(self, ctx: FileContext, extra_categories: list[str]) -> Classification:
        text = ctx.text.lower()
        name = ctx.path.stem.lower().replace("_", " ").replace("-", " ")
        best: tuple[int, tuple[str, str, list[str], list[str]]] | None = None
        for rule in KEYWORD_RULES:
            score = sum(2 if kw in name else 0 for kw in rule[2]) + sum(1 for kw in rule[2] if kw in text)
            if score and (best is None or score > best[0]):
                best = (score, rule)

        date_found = find_date(ctx.path.stem, ctx.text)
        vendor = find_vendor(ctx.text, ctx.path.name)

        if best:
            score, (category, doc_type, _kw, tags) = best
            amount, currency = find_amount(ctx.text) if category.startswith("Finanzen") else (None, None)
            return Classification(
                category=category, doc_type=doc_type, title=doc_type, vendor=vendor, date=date_found,
                amount=amount, currency=currency, tags=list(tags), confidence=min(0.9, 0.45 + 0.1 * score),
                source="heuristic",
            )

        name_lower = ctx.path.name.lower()
        if ctx.ext in IMAGE_EXTENSIONS and ("screenshot" in name_lower or "bildschirmfoto" in name_lower):
            return Classification(category="Screenshots", doc_type="Screenshot", title="Screenshot",
                                  date=date_found, tags=["screenshot"], confidence=0.9, source="heuristic")
        category, doc_type = EXTENSION_CATEGORIES.get(ctx.ext, ("Sonstiges", ctx.ext.lstrip(".").upper() or "Datei"))
        confidence = 0.8 if ctx.ext in EXTENSION_CATEGORIES and category != "Dokumente" else 0.5
        return Classification(category=category, doc_type=doc_type, title=doc_type, vendor=vendor,
                              date=date_found, tags=[category.split("/")[0].lower()], confidence=confidence,
                              source="heuristic")
