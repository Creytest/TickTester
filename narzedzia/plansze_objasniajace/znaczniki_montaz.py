"""Znaczniki do montażu (DaVinci): okręgi, ramki i strzałki w prawo, PNG z przezroczystym tłem.
Kolory kanału: zielony #00D084, czerwony #FF3B30, biały #F2F2F2.

Uruchomienie (z głównego folderu repo):
    python narzedzia/plansze_objasniajace/znaczniki_montaz.py
→ nagrania/_montaz/znaczniki/ (okrag_<kolor>[_bardzo_gruby], ramka_*, strzalki/strzalka_<kolor>_<nachylenie>.png)

W DaVinci: PNG na ścieżkę V2 nad nagraniem, Inspector → Transform (Position, Zoom,
Rotation Angle dla kąta pośredniego), fade ~5 klatek na początku i końcu.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "nagrania" / "_montaz" / "znaczniki"
S = 4  # nadpróbkowanie (gładkie krawędzie)
KOLORY = {"zielony": (0, 208, 132, 255), "czerwony": (255, 59, 48, 255), "bialy": (242, 242, 242, 255)}
STRZALKA = {"zielony": "zielona", "czerwony": "czerwona", "bialy": "biala"}
KATY = [60, 45, 30, 15, 0, -15, -30, -45, -60]  # dodatni = w górę, ujemny = w dół; zawsze w prawo


def nazwa_kata(a):
    return "poziomo" if a == 0 else (f"gora_{a}st" if a > 0 else f"dol_{-a}st")


# Grubość obwódki w px na kanwie 400×400. Okrąg mocno pomniejszany w DaVinci (małe rzeczy na ekranie)
# traci grubość proporcjonalnie, więc linia jest gruba: 40 px = po Zoom 0,25 nadal ~10 px.
OKRAG_GRUBOSC = {"": 40, "_bardzo_gruby": 70}


def okrag(c, path, grubosc=40):
    im = Image.new("RGBA", (400 * S, 400 * S), (0, 0, 0, 0))
    m = grubosc // 2 + 4  # margines, żeby obwódka nie wychodziła poza kanwę
    ImageDraw.Draw(im).ellipse([m * S, m * S, (400 - m) * S, (400 - m) * S], outline=c, width=grubosc * S)
    im.resize((400, 400), Image.LANCZOS).save(path)


def ramka(c, path):
    im = Image.new("RGBA", (800 * S, 240 * S), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([10 * S, 10 * S, 790 * S, 230 * S], radius=40 * S, outline=c, width=12 * S)
    im.resize((800, 240), Image.LANCZOS).save(path)


def strzalka(c, kat, path, n=400):
    im = Image.new("RGBA", (n * S, n * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = math.radians(kat)
    ux, uy = math.cos(r), -math.sin(r)
    px, py = -uy, ux
    cx = cy = n * S / 2
    L, hl, hw = 170 * S, 80 * S, 55 * S
    tx, ty = cx + ux * L, cy + uy * L          # grot
    bx, by = cx - ux * L, cy - uy * L          # początek
    hx, hy = tx - ux * hl, ty - uy * hl        # podstawa grotu
    d.line([bx, by, hx, hy], fill=c, width=22 * S)
    d.ellipse([bx - 11 * S, by - 11 * S, bx + 11 * S, by + 11 * S], fill=c)
    d.polygon([(tx, ty), (hx + px * hw, hy + py * hw), (hx - px * hw, hy - py * hw)], fill=c)
    im.resize((n, n), Image.LANCZOS).save(path)


def podglad(path):
    P = Image.new("RGBA", (9 * 180, 3 * 180), (11, 13, 16, 255))
    for j, k in enumerate(KOLORY):
        for i, a in enumerate(KATY):
            im = Image.open(OUT / "strzalki" / f"strzalka_{STRZALKA[k]}_{nazwa_kata(a)}.png").resize((180, 180))
            P.alpha_composite(im, (i * 180, j * 180))
    P.convert("RGB").save(path)


def main():
    (OUT / "strzalki").mkdir(parents=True, exist_ok=True)
    for k, c in KOLORY.items():
        for sufiks, g in OKRAG_GRUBOSC.items():
            okrag(c, OUT / f"okrag_{k}{sufiks}.png", g)
        ramka(c, OUT / f"ramka_{k}.png")
        for a in KATY:
            strzalka(c, a, OUT / "strzalki" / f"strzalka_{STRZALKA[k]}_{nazwa_kata(a)}.png")
    podglad(OUT / "strzalki_podglad.jpg")
    print("ok", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
