
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

ASSETS = {
    "USA 100": Path(
        r"D:\Tickdata\USA_100_Technical_Index_GMT+2_US-DST.csv"
    ),
    "XAUUSD": Path(
        r"D:\Tickdata\XAUUSD_GMT+2_US-DST.csv"
    ),
    "Bitcoin": Path(
        r"D:\Tickdata\Bitcoin_vs_US_Dollar_GMT+2_US-DST.csv"
    ),
    "EURUSD": Path(
        r"D:\Tickdata\EURUSD_GMT+2_US-DST.csv"
    ),
    "Brent": Path(
        r"D:\Tickdata\US_Brent_Crude_Oil_GMT+2_US-DST.csv"
    ),
    # Folder z plikami na każdy rok (Dukascopy, już w GMT+2 z US-DST).
    # Dane od 2021-11-01.
    "US500": Path(
        r"D:\Tickdata\USA500IDXUSD"
    ),
}

# True oznacza, że plik zapisuje najpierw wyższą cenę,
# a potem niższą. W loaderze zamienimy je na Bid i Ask.
REVERSE_BID_ASK = {
    "USA 100": False,  # nierozstrzygnięte — ceny są równe
    "XAUUSD": True,
    "Bitcoin": True,
    "EURUSD": True,
    "Brent": True,
    "US500": False,  # kolumny: Bid, Ask
}

TIMEFRAMES = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
}

INITIAL_CAPITAL = 10_000.0
RISK_PER_TRADE = 0.01
SLIPPAGE_TICKS = 1

# Prowizja jako ułamek wartości pozycji, pobierana przy wejściu
# i przy wyjściu (0.0001 = 0,01% za stronę). Spread jest już
# w danych Bid/Ask, więc wpisujemy tylko koszt ponad spread.
# Wartości przybliżone: 0,0035% to ok. 3,5 USD za lota EURUSD
# na rachunku typu Raw; złoto i ropa mają ten sam procent
# (ostrożniej niż 3,5 USD za lota). BTC: typowa prowizja giełdowa.
COMMISSION = {
    "USA 100": 0.00006,  # dane bez spreadu (Bid = Ask) — prowizja go zastępuje
    "XAUUSD": 0.000035,
    "Bitcoin": 0.0005,
    "EURUSD": 0.000035,
    "Brent": 0.000035,
    "US500": 0.000035,
}

# Najmniejsza zmiana ceny; poślizg = SLIPPAGE_TICKS * TICK_SIZE.
TICK_SIZE = {
    "USA 100": 0.01,
    "XAUUSD": 0.01,
    "Bitcoin": 0.01,
    "EURUSD": 0.00001,
    "Brent": 0.001,
    "US500": 0.01,
}
