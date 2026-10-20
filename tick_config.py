
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
}

# True oznacza, że plik zapisuje najpierw wyższą cenę,
# a potem niższą. W loaderze zamienimy je na Bid i Ask.
REVERSE_BID_ASK = {
    "USA 100": False,  # nierozstrzygnięte — ceny są równe
    "XAUUSD": True,
    "Bitcoin": True,
    "EURUSD": True,
    "Brent": True,
}

TIMEFRAMES = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
}

INITIAL_CAPITAL = 10_000.0
RISK_PER_TRADE = 0.01
COMMISSION = 0.0005
SLIPPAGE_TICKS = 1
