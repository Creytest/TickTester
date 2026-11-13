"""
Gdzie zapisywać materiały do odcinka.

Wszystko do jednego odcinka leży w nagrania/<Odcinek>/<Strategia>/:
    plansza_zasady.png, grafiki       — w gicie (robione skryptami z narzedzia/plansze_objasniajace/),
    wyniki/                           — backtest z run_all_assets.py (HTML, CSV, plansze wyników),
    wyniki_Control/, wyniki_Standard/ — grupy kontrolne tej strategii,
    wyniki_event_study/               — badania zdarzeń.
Foldery wyniki*/ są tworzone u Ciebie na komputerze i nie trafiają do gita
(są duże i liczone z ticków), tak jak wcześniej wyniki/.

Odcinek wynika z folderu strategii w strategies/:
    strategies/tiktok/EMA9.py → nagrania/TikTok/EMA9/
Wyjątki dopisz w ODCINEK_STRATEGII.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAGRANIA = ROOT / "nagrania"

# Folder w strategies/ → folder odcinka w nagrania/.
ODCINEK_ZRODLA = {
    "tiktok": "TikTok",
    "reddit": "Reddit",
    "tradingview": "TradingView",
    "tradingview_porownawcze": "TradingViewPorownawcze",
    "ksiazki": "Ksiazki",
}

# Strategie, które idą do innego odcinka niż ich folder, np. {"RSI_90": "RSI"}.
ODCINEK_STRATEGII: dict[str, str] = {}

# Warianty liczone razem ze strategią: zapisują się w jej folderze.
WARIANTY = ("_Control", "_Standard")


def _bez_tick(name: str) -> str:
    return name[len("tick_"):] if name.startswith("tick_") else name


def podziel(name: str) -> tuple[str, str]:
    """("SqueezeBreakoutSignals_Control") → ("SqueezeBreakoutSignals", "_Control")."""
    name = _bez_tick(name)
    for suffix in WARIANTY:
        if name.endswith(suffix):
            return name[: -len(suffix)], suffix
    return name, ""


def odcinek(name: str) -> str:
    """Nazwa folderu odcinka dla strategii."""
    base, _ = podziel(name)
    for key in (_bez_tick(name), base):
        if key in ODCINEK_STRATEGII:
            return ODCINEK_STRATEGII[key]
    strategies = ROOT / "strategies"
    for source, episode in ODCINEK_ZRODLA.items():
        if (strategies / source / f"{_bez_tick(name)}.py").exists():
            return episode
    return "Inne"


def folder_strategii(name: str) -> Path:
    """nagrania/<Odcinek>/<Strategia>/ — warianty _Control/_Standard trafiają do strategii bazowej."""
    base, _ = podziel(name)
    return NAGRANIA / odcinek(name) / base


def folder_wynikow(name: str) -> Path:
    """nagrania/<Odcinek>/<Strategia>/wyniki/ (albo wyniki_Control/, wyniki_Standard/)."""
    _, suffix = podziel(name)
    return folder_strategii(name) / f"wyniki{suffix}"


def folder_badania(odcinek_name: str, *parts: str) -> Path:
    """Badanie bez jednej strategii, np. folder_badania("FormacjeSwiecowe", "wyniki_event_study")."""
    return NAGRANIA.joinpath(odcinek_name, *parts)
