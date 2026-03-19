"""
System-wide constants for the UPST Quant Finance Hub.
"""

# ── Target Securities ──
UPST_TICKER = "UPST"
SPY_TICKER = "SPY"
BENCHMARK_TICKERS = ["SPY", "QQQ", "XLF", "ARKF"]

# ── Peer Universe ──
UPST_PEERS = ["SOFI", "LC", "AFRM", "HOOD", "PYPL", "MQ", "LPRO"]

# ── Technical Defaults ──
MA_PERIODS = [10, 20, 50, 100, 200]
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
ATR_PERIOD = 14
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2.0
ADX_PERIOD = 14

# ── Rolling Windows ──
ROLLING_BETA_WINDOW = 63  # ~3 months
ROLLING_CORR_WINDOW = 63
ROLLING_VOL_WINDOW = 21

# ── Risk Defaults ──
RISK_FREE_RATE = 0.05  # Updated from FRED at runtime
MAX_POSITION_PCT = 0.10  # 10% of portfolio
MAX_LOSS_PCT = 0.02  # 2% risk per trade
KELLY_FRACTION = 0.25  # Quarter-Kelly for safety

# ── Scoring Weights (default — adjustable at runtime) ──
COMPOSITE_WEIGHTS = {
    "technical_strength": 0.12,
    "options_sentiment": 0.10,
    "short_opportunity": 0.08,
    "squeeze_risk": -0.08,  # Negative = squeeze hurts short thesis
    "funding_strength": 0.12,
    "origination_momentum": 0.10,
    "macro_pressure": -0.08,
    "credit_stress": -0.06,
    "valuation_attractiveness": 0.10,
    "news_regime": 0.06,
    "forecast_confidence": 0.06,
    "relative_strength_spy": 0.06,
    "trade_quality": 0.04,
    "positioning_fragility": -0.04,
}

# ── Timeframes ──
TIMEFRAMES = ["intraday", "daily", "weekly", "monthly"]

# ── Data Quality Thresholds ──
STALE_PRICE_MINUTES = 15
STALE_OPTIONS_MINUTES = 30
STALE_SHORT_HOURS = 24
STALE_MACRO_HOURS = 48
STALE_NEWS_HOURS = 6

# ── Monte Carlo ──
MC_DEFAULT_PATHS = 10_000
MC_DEFAULT_HORIZON_DAYS = 63  # ~3 months

# ── Forecast Validation ──
BRIER_GOOD_THRESHOLD = 0.25
CALIBRATION_BINS = 10
