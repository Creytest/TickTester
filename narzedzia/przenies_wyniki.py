"""
Jednorazowo: przenosi stare wyniki z wyniki/ do nagrania/<Odcinek>/<Strategia>/.

    wyniki/<Strategia>/              → nagrania/<Odcinek>/<Strategia>/wyniki/
    wyniki/<Strategia>_Control/      → nagrania/<Odcinek>/<Strategia>/wyniki_Control/
    wyniki/event_study_AutoLevels/   → nagrania/TradingViewPorownawcze/AutoLevelsTrendlines/wyniki_event_study/
    wyniki/KeyLevelZones/            → (to samo co strategia KeyLevelZones; zdarzenia_*.csv idą do wyniki_event_study/)
    wyniki/event_study_Wyckoff/      → nagrania/TradingView/Wyckoff/wyniki_event_study/
    wyniki/event_study_RSI/          → nagrania/RSI/wyniki_event_study/
    wyniki/event_study_candles*/     → nagrania/FormacjeSwiecowe/wyniki_event_study*/
    wyniki/podglad_formacji*/        → nagrania/FormacjeSwiecowe/wyniki_podglad*/

Uruchomienie (z głównego folderu repo):
    python narzedzia/przenies_wyniki.py          — tylko pokazuje, co zrobi,
    python narzedzia/przenies_wyniki.py --tak    — przenosi.
Plik, który już istnieje w miejscu docelowym, zostaje nietknięty (stary zostaje w wyniki/).
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from narzedzia.odcinki import ROOT, folder_badania, folder_strategii, folder_wynikow, odcinek

OLD = ROOT / "wyniki"

STALE = {
    "event_study_AutoLevels": folder_strategii("AutoLevelsTrendlines") / "wyniki_event_study",
    "event_study_Wyckoff": folder_strategii("Wyckoff") / "wyniki_event_study",
    "event_study_RSI": folder_badania("RSI", "wyniki_event_study"),
    "event_study_candles": folder_badania("FormacjeSwiecowe", "wyniki_event_study"),
    "event_study_candles_plansza": folder_badania("FormacjeSwiecowe", "wyniki_event_study_plansza"),
    "podglad_formacji": folder_badania("FormacjeSwiecowe", "wyniki_podglad"),
    "podglad_formacji_plansza": folder_badania("FormacjeSwiecowe", "wyniki_podglad_plansza"),
}


def target(folder: Path) -> Path | None:
    if folder.name in STALE:
        return STALE[folder.name]
    if odcinek(folder.name) != "Inne":
        return folder_wynikow(folder.name)
    return None


def move_tree(src: Path, dst: Path, run: bool) -> tuple[int, int]:
    moved = skipped = 0
    for file in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = file.relative_to(src)
        # Stare event study Key Level Zones leżało razem z backtestem.
        if src.name == "KeyLevelZones" and file.parent == src and file.name.startswith("zdarzenia_"):
            out = folder_strategii("KeyLevelZones") / "wyniki_event_study" / rel
        elif src.name == "KeyLevelZones" and file.parent == src and file.name.startswith("podsumowanie_") \
                and not file.name.startswith("podsumowanie_KeyLevelZones"):
            out = folder_strategii("KeyLevelZones") / "wyniki_event_study" / rel
        else:
            out = dst / rel
        if out.exists():
            skipped += 1
            continue
        moved += 1
        if run:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file), str(out))
    return moved, skipped


def main():
    run = "--tak" in sys.argv
    if not OLD.exists():
        print("Brak folderu wyniki/ — nie ma czego przenosić.")
        return

    unknown = []
    for folder in sorted(p for p in OLD.iterdir() if p.is_dir()):
        dst = target(folder)
        if dst is None:
            unknown.append(folder.name)
            continue
        moved, skipped = move_tree(folder, dst, run)
        note = f", {skipped} już było w miejscu docelowym" if skipped else ""
        print(f"{folder.name:40s} → {dst.relative_to(ROOT)}  (plików: {moved}{note})")

    loose = [p.name for p in OLD.iterdir() if p.is_file()]
    if unknown or loose:
        print("\nZostaje w wyniki/ (nie wiem, do którego odcinka):")
        for name in unknown + loose:
            print("   ", name)

    if run:
        # Usuwa puste foldery po przeniesieniu.
        for folder in sorted(OLD.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
        if OLD.exists() and not any(OLD.iterdir()):
            OLD.rmdir()
        print("\nGotowe.")
    else:
        print("\nTo był podgląd. Żeby przenieść: python narzedzia/przenies_wyniki.py --tak")


if __name__ == "__main__":
    main()
