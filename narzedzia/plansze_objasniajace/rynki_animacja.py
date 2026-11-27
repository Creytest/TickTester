"""Plansza 'NA CZYM TESTUJĘ' jako zapętlone MP4 obok PNG: całość od razu widoczna, 1:1 z PNG,
tylko subtelny efekt „życia”. 1920x1080, 30 kl./s, BT.709 (jak wyniki_animacja.py).

Efekt (Kamil, 2026-11-26): na początku pętli po kafelkach i napisach przelatuje jeden miękki,
ukośny połysk; wszystkie zielone elementy (kropki z poświatą, kreski nad symbolami) cały czas
razem rozjaśniają się i wracają (co ~2,5 s). --efekt polysk / puls = tylko jedno z dwóch.
Pętla jest bezszwowa — w DaVinci wystarczy skopiować klip albo wydłużyć go z Loop.

Uruchomienie (z głównego folderu repo):
    python narzedzia/plansze_objasniajace/rynki_animacja.py               # wszystkie plansze rynków
    python narzedzia/plansze_objasniajace/rynki_animacja.py EMA9 IBS_MeanReversion
    python narzedzia/plansze_objasniajace/rynki_animacja.py --lista
→ obok każdej planszy z rynki_plansza.py: nagrania/<Odcinek>/<Strategia>/plansza_rynki.png + .mp4
(PNG zapisuje się od nowa, więc para zawsze do siebie pasuje).
Plansze wyników (plansze_*/0_rynki.mp4) robi wyniki_animacja.py tą samą funkcją.
"""
import argparse
import contextlib
import io
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import rynki_plansza as rp  # noqa: E402

FPS = 30
W, H = 1920, 1080
YUV_BT709 = ["-vf", "scale=out_color_matrix=bt709:out_range=tv", "-pix_fmt", "yuv420p",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
BG_RGB = np.array([0x0B, 0x0D, 0x10], dtype=np.float32)

POLYSK_SILA = 0.35      # ile maksymalnie rozjaśnia (część drogi do bieli)
POLYSK_SZEROKOSC = 140  # px, połowa szerokości miękkiego pasa
POLYSK_CZAS = 0.45      # część pętli, w której pas przelatuje; resztę plansza stoi
HALO_MOCNE = 0.60       # krycie poświaty w szczycie pulsu (PNG ma 0.18)
PULS_SILA = 0.55        # rozjaśnienie zieleni w szczycie pulsu (część drogi do bieli)
PULS_CYKLE = 2          # ile razy zieleń rozjaśnia się w jednej pętli (5 s → co 2,5 s)


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def render(assets, timeframes, period, halo):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "p.png"
        with contextlib.redirect_stdout(io.StringIO()):
            rp.plansza(assets, timeframes, p, period, halo=halo)
        return np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)


def animacja(assets, timeframes, period, out, efekt="oba", sekundy=5.0, png=True):
    """out: ścieżka .mp4; png=True zapisuje obok też statyczną planszę (.png, = rynki_plansza)."""
    base = render(assets, timeframes, period, 0.18)
    strong = render(assets, timeframes, period, HALO_MOCNE) if efekt in ("puls", "oba") else base
    out = Path(out).with_suffix(".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    if png:
        Image.fromarray(base.astype(np.uint8)).save(out.with_suffix(".png"))

    # Maska „treści”: połysk tylko na tym, co odstaje od tła (ramki, kafelki, napisy, kropki).
    diff = np.abs(base - BG_RGB).max(axis=2)
    mask = np.clip(diff / 60.0, 0, 1)[..., None]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    diag = xx + 0.35 * yy                      # lekko ukośny pas
    d_min, d_max = -POLYSK_SZEROKOSC * 2, diag.max() + POLYSK_SZEROKOSC * 2
    # Maska zieleni (#00D084 i jej poświata): G wyraźnie ponad R i B.
    green = np.clip((base[..., 1] - np.maximum(base[..., 0], base[..., 2]) - 20) / 80.0, 0, 1)[..., None]

    n = int(round(sekundy * FPS))
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-b:v", "12M",
           *YUV_BT709, str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        t = i / n
        frame = base
        if efekt in ("puls", "oba"):
            # wszystkie zielone razem; pełne cykle w pętli → bez szwu
            w = 0.5 - 0.5 * np.cos(2 * np.pi * PULS_CYKLE * t)
            frame = base + (strong - base) * w
            gm = np.clip((frame[..., 1] - np.maximum(frame[..., 0], frame[..., 2]) - 20) / 80.0, 0, 1)[..., None]
            frame = frame + (255.0 - frame) * np.maximum(gm, green) * PULS_SILA * w
        if efekt in ("polysk", "oba") and t < POLYSK_CZAS:
            s = t / POLYSK_CZAS
            s = s * s * (3 - 2 * s)
            pos = d_min + (d_max - d_min) * s
            band = np.exp(-((diag - pos) / POLYSK_SZEROKOSC) ** 2)[..., None]
            frame = frame + (255.0 - frame) * band * mask * POLYSK_SILA
        proc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError(f"ffmpeg zakończył się błędem przy {out}")
    print("  ", out.relative_to(ROOT) if out.is_relative_to(ROOT) else out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("strategie", nargs="*", help="foldery strategii (domyślnie wszystkie plansze)")
    ap.add_argument("--efekt", choices=["polysk", "puls", "oba"], default="oba")
    ap.add_argument("--sekundy", type=float, default=5.0)
    ap.add_argument("--lista", action="store_true")
    a = ap.parse_args()
    cele = rp.cele()
    if a.lista:
        for _, _, path, _ in cele:
            print(path.relative_to(ROOT))
        return
    if a.strategie:
        cele = [c for c in cele if c[2].parent.name in a.strategie]
        if not cele:
            sys.exit("Nie ma takich strategii (--lista pokazuje wszystkie).")
    for assets, timeframes, path, period in cele:
        animacja(assets, timeframes, period, path.with_suffix(".mp4"), a.efekt, a.sekundy)
    print(f"Gotowe: {len(cele)}")


if __name__ == "__main__":
    main()
