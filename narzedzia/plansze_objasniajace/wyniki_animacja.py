"""Animowane plansze wyników strategii — 1:1 jak PNG z narzedzia/plansze.py (MP4 1920×1080, 30 kl./s).

    1_mediany.mp4          — plansza 1_mediany: trzy duże liczby wchodzą po kolei
                             (pojawiają się i odliczają od zera do wartości z planszy),
    2_wykres_kapitalu.mp4  — plansza 2_wykres_kapitalu: krzywe kapitału rysują się od lewej
                             do prawej, podpisy (mediana, najlepsza, najgorsza) na końcu.
Figury buduje ten sam kod co PNG (plansze.medians_figure / equity_figure), więc ostatnia
klatka = plansza PNG. Tabela (3_tabela.png) zostaje statyczna.

Użycie:
    python narzedzia/plansze_objasniajace/wyniki_animacja.py BigBeluga_Stoch_80percent
    python narzedzia/plansze_objasniajace/wyniki_animacja.py BigBeluga_Stoch_80percent --sekundy 1 2 3
    python narzedzia/plansze_objasniajace/wyniki_animacja.py BigBeluga_Stoch_80percent --testowe   # bez wyników
    python narzedzia/plansze_objasniajace/wyniki_animacja.py --wszystkie             # każda strategia z wynikami
    python narzedzia/plansze_objasniajace/wyniki_animacja.py --wszystkie --odcinek TikTok
Opcje: --sekundy (czas animacji, domyślnie 2; kilka wartości = kilka wersji),
       --trzymaj (sekundy stopklatki na końcu, domyślnie 1), --claim-win-rate 90, --png (tylko PNG).
Wyniki: nagrania/<Odcinek>/<Strategia>/wyniki/animacja/ (z --testowe: animacja_dane_testowe/).
Dane: podsumowanie_<Strategia>_*.csv i *_kapital.csv z run_all_assets, MIN_TRADES strategii.
Wideo wymaga ffmpeg: w PATH albo `pip install imageio-ffmpeg`.
"""
from __future__ import annotations

import argparse
import importlib
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from narzedzia import plansze as P  # noqa: E402  (ładuje też fonty i kolory)
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.animation import FFMpegWriter  # noqa: E402

# Anton/Inter z repo — jak w run_all_assets (przez rynki_plansza), więc fonty = PNG.
for _f in (Path(__file__).resolve().parent / "fonts").glob("*.[ot]tf"):
    font_manager.fontManager.addfont(str(_f))

from narzedzia.odcinki import NAGRANIA, folder_wynikow  # noqa: E402

FPS = 30
# RGB → YUV wg BT.709 i oznaczenie pliku jako BT.709. Bez tego ffmpeg liczy BT.601,
# a DaVinci/odtwarzacze czytają HD jako BT.709 — czerwony #FF3B30 robi się pomarańczowy.
YUV_BT709 = ["-vf", "scale=out_color_matrix=bt709:out_range=tv", "-pix_fmt", "yuv420p",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
RYSOWANIE = 0.85  # część czasu na rysowanie krzywych (stałe tempo); reszta na wejście podpisów
LICZBA = 0.5      # część czasu na wejście jednej liczby (kolejne startują co 1/4 czasu)


def ease(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ============================================================
# DANE
# ============================================================

def _modul(strategy: str):
    for path in (ROOT / "strategies").rglob(f"{strategy}.py"):
        return importlib.import_module(".".join(path.relative_to(ROOT).with_suffix("").parts))
    sys.exit(f"Nie znaleziono strategies/**/{strategy}.py")


def wczytaj(strategy: str):
    """(podsumowanie OK, krzywe {(aktywo, interwał): DataFrame}, okres „2021–2025”) z run_all_assets."""
    folder = folder_wynikow(strategy)
    pliki = sorted(folder.glob(f"podsumowanie_{strategy}_*.csv"), key=lambda p: p.stat().st_mtime)
    if not pliki:
        sys.exit(f"Brak podsumowania w {folder}. Najpierw run_all_assets dla {strategy} "
                 f"(albo --testowe).")
    table = pliki[-1]
    start, end = table.stem.removeprefix(f"podsumowanie_{strategy}_").split("_")
    data = pd.read_csv(table, sep=";", decimal=",")
    data = data[data["status"] == "OK"].reset_index(drop=True)
    equities = {}
    for asset, tf in zip(data["asset"], data["timeframe"]):
        path = folder / f"{strategy}_{str(asset).replace(' ', '_')}_{tf}_{start}_{end}_kapital.csv"
        if path.exists():
            equities[(asset, tf)] = pd.read_csv(path, sep=";", decimal=",")
        else:
            print(f"Brak krzywej {path.name} — pominięta")
    return data, equities, f"{start[:4]}–{end[:4]}"


# Dane testowe: wyniki końcowe, Win Rate i PF z planszy BigBeluga Two-Pole + Stochastic 7,3,3
# (zrzut Kamila 2026-11-26); przebieg krzywych między startem a końcem wymyślony.
TESTOWE = [
    ("XAUUSD", "15m", -99.8, 27.8, 0.55), ("XAUUSD", "1h", -70.1, 29.2, 0.63),
    ("XAUUSD", "4h", -21.6, 29.5, 0.69), ("BTCUSDT", "15m", -100.0, 30.3, 0.46),
    ("BTCUSDT", "1h", -86.1, 31.6, 0.55), ("BTCUSDT", "4h", -16.4, 34.1, 0.80),
    ("EURUSD", "15m", -100.0, 31.2, 0.52), ("EURUSD", "1h", -78.5, 29.7, 0.62),
    ("EURUSD", "4h", -22.4, 32.1, 0.75), ("Brent", "15m", -99.9, 25.6, 0.43),
    ("Brent", "1h", -85.4, 23.8, 0.45), ("Brent", "4h", -14.1, 32.6, 0.85),
    ("US500", "15m", -100.0, 25.9, 0.44), ("US500", "1h", -67.5, 31.4, 0.67),
    ("US500", "4h", -7.0, 33.3, 0.91),
]


def testowe():
    rng = np.random.default_rng(7)
    idx = pd.date_range("2021-01-01", "2025-12-31", freq="1D")
    t = np.linspace(0, 1, len(idx))
    rows, equities = [], {}
    for asset, tf, ret, wr, pf in TESTOWE:
        target = np.log(max(1 + ret / 100, 2e-4))
        k = {"15m": 6.0, "1h": 1.5, "4h": 0.3}[tf]               # niższy interwał = szybszy spadek
        trend = target * (1 - np.exp(-k * t)) / (1 - np.exp(-k))
        noise = np.cumsum(rng.normal(0, 0.006, len(idx)))
        noise -= t * noise[-1]                                   # most: koniec dokładnie w wyniku
        equities[(asset, tf)] = pd.DataFrame({"timestamp": idx, "equity": 10_000 * np.exp(trend + noise)})
        rows.append({"asset": asset, "timeframe": tf, "status": "OK", "return_%": ret,
                     "win_rate_%": wr, "profit_factor": pf, "trades": 100})
    return pd.DataFrame(rows), equities, "2021–2025"


# ============================================================
# RENDER
# ============================================================

FFMPEG = "ffmpeg"


def ffmpeg_ok() -> bool:
    global FFMPEG
    try:
        import imageio_ffmpeg
        FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
        return True
    except ImportError:
        return shutil.which("ffmpeg") is not None


def render(fig, update, sekundy: float, trzymaj: float, path: Path, video: bool) -> None:
    if video:
        # plt.style.context("default") resetuje rcParams, więc ścieżkę ustawiamy tuż przed zapisem.
        matplotlib.rcParams["animation.ffmpeg_path"] = FFMPEG
        writer = FFMpegWriter(fps=FPS, codec="libx264", bitrate=12000, extra_args=YUV_BT709)
        with writer.saving(fig, str(path.with_suffix(".mp4")), dpi=P.DPI):
            for k in range(int(round((sekundy + trzymaj) * FPS))):
                update(k / FPS)
                writer.grab_frame(facecolor=P.BLACK)
        print(f"  {path.with_suffix('.mp4')}")
    update(sekundy)
    fig.savefig(path.with_suffix(".png"), dpi=P.DPI, facecolor=P.BLACK)
    plt.close(fig)


def anim_mediany(fig, numbers, sekundy: float):
    """Liczby po kolei: każda się pojawia i odlicza od zera; podpis wchodzi razem z nią."""
    step = (1 - LICZBA) / max(len(numbers) - 1, 1)

    def update(t):
        for i, (text, label, value, fmt) in enumerate(numbers):
            a = ease((t / sekundy - i * step) / LICZBA)
            text.set_alpha(a)
            label.set_alpha(a)
            ok = value is not None and pd.notna(value) and np.isfinite(value)
            text.set_text(fmt(value * a) if ok and a < 1 else fmt(value))
    return update


def anim_krzywe(fig, sekundy: float):
    """Krzywe (gid="krzywa") rysują się od lewej do prawej, potem wchodzą podpisy."""
    ax = fig.axes[0]
    ax.set_xlim(ax.get_xlim())          # osie jak na końcowej planszy, nie skaczą
    ax.set_ylim(ax.get_ylim())
    lines = [(ln, ln.get_xdata(), ln.get_ydata()) for ln in ax.lines if ln.get_gid() == "krzywa"]
    texts = list(ax.texts)
    n = max((len(x) for _, x, _ in lines), default=1)

    def update(t):
        a = min(max(t / (sekundy * RYSOWANIE), 0.0), 1.0)   # liniowo: bez zwalniania na końcu
        k = max(1, int(round(a * (n - 1))) + 1)
        for ln, x, y in lines:
            ln.set_data(x[:k], y[:k])
        b = ease((t / sekundy - RYSOWANIE) / (1 - RYSOWANIE))
        for txt in texts:
            txt.set_alpha(b)
    return update


def strategie_z_wynikami(odcinek: str | None = None) -> list[str]:
    """Strategie z podsumowaniem run_all_assets w nagrania/<Odcinek>/<Strategia>/wyniki*/."""
    names = []
    for table in sorted(NAGRANIA.glob("*/*/wyniki*/podsumowanie_*.csv")):
        if odcinek and table.parts[-4].lower() != odcinek.lower():
            continue
        # podsumowanie_<Strategia>_<start>_<koniec>.csv
        name = table.stem.removeprefix("podsumowanie_").rsplit("_", 2)[0]
        if name not in names:
            names.append(name)
    return names


def animuj(strategy: str, args, video: bool) -> None:
    module = _modul(strategy)
    title = getattr(module, "NAME", strategy)
    claim = args.claim_win_rate if args.claim_win_rate is not None else getattr(module, "CLAIM_WIN_RATE", None)
    summary, equities, period = testowe() if args.testowe else wczytaj(strategy)
    _, counted, _, subtitle, note = P.plansze_context(summary, period, getattr(module, "MIN_TRADES", None))

    out = folder_wynikow(strategy) / ("animacja_dane_testowe" if args.testowe else "animacja")
    out.mkdir(parents=True, exist_ok=True)
    print(f"{title} → {out}")
    for s in args.sekundy:
        tag = f"{s:g}s".replace(".", ",")
        with plt.style.context("default"):
            fig, numbers = P.medians_figure(counted, title, subtitle, claim, note)
            render(fig, anim_mediany(fig, numbers, s), s, args.trzymaj, out / f"1_mediany_{tag}", video)
            fig = P.equity_figure(counted, equities, title, subtitle, note)
            render(fig, anim_krzywe(fig, s), s, args.trzymaj, out / f"2_wykres_kapitalu_{tag}", video)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("strategia", nargs="?")
    ap.add_argument("--wszystkie", action="store_true", help="każda strategia z wynikami w nagrania/")
    ap.add_argument("--odcinek", help="z --wszystkie: tylko ten odcinek, np. TikTok")
    ap.add_argument("--sekundy", type=float, nargs="+", default=[2.0])
    ap.add_argument("--trzymaj", type=float, default=1.0)
    ap.add_argument("--claim-win-rate", type=float, default=None)
    ap.add_argument("--testowe", action="store_true")
    ap.add_argument("--png", action="store_true")
    args = ap.parse_args()

    video = not args.png
    if video and not ffmpeg_ok():
        sys.exit("Brak ffmpeg. Zainstaluj: pip install imageio-ffmpeg (albo dopisz --png).")
    if args.wszystkie:
        names = strategie_z_wynikami(args.odcinek)
        if not names:
            sys.exit("Brak wyników run_all_assets w nagrania/ (podsumowanie_*.csv).")
    elif args.strategia:
        names = [args.strategia]
    else:
        ap.error("podaj strategię albo --wszystkie")
    bledy = []
    for name in names:
        try:
            animuj(name, args, video)
        except (SystemExit, Exception) as err:      # jedna zepsuta strategia nie zatrzymuje reszty
            if len(names) == 1:
                raise
            plt.close("all")
            print(f"{name}: pominięta — {err}")
            bledy.append(name)
    if len(names) > 1:
        print(f"Gotowe: {len(names) - len(bledy)}/{len(names)}" + (f", pominięte: {', '.join(bledy)}" if bledy else ""))


if __name__ == "__main__":
    main()
