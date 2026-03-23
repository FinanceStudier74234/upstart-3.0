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

# ── Score Formulas Reference ──
# Each score formula is documented here for transparency.
# All scores range 0-100.
SCORE_FORMULAS = {
    "funding_strength": {
        "description": "Funding health and capacity assessment",
        "weights": {"capacity": 0.25, "coverage": 0.20, "diversification": 0.15,
                    "maturity": 0.15, "renewal": 0.15, "covenants": 0.10},
        "direction": "higher_is_better",
    },
    "origination_momentum": {
        "description": "Business origination growth and acceleration",
        "weights": {"qoq_growth": 0.30, "yoy_growth": 0.25, "volume": 0.20,
                    "acceleration": 0.15, "product_diversity": 0.10},
        "direction": "higher_is_better",
    },
    "macro_pressure": {
        "description": "Macro environment stress level",
        "weights": {"fed_funds": 0.20, "yield_curve": 0.15, "hy_spreads": 0.20,
                    "unemployment": 0.15, "recession_prob": 0.15, "lending_standards": 0.15},
        "direction": "higher_is_worse",
    },
    "credit_stress": {
        "description": "Consumer credit and lending stress",
        "weights": {"delinquency": 0.30, "hy_spread": 0.25,
                    "lending_standards": 0.25, "consumer_credit": 0.20},
        "direction": "higher_is_worse",
    },
    "valuation_attractiveness": {
        "description": "Relative and absolute valuation assessment",
        "weights": {"ps_vs_history": 0.25, "ps_vs_peers": 0.20, "ev_revenue": 0.15,
                    "growth_adjusted": 0.20, "fcf_yield": 0.10, "fair_value_gap": 0.10},
        "direction": "higher_is_better",
    },
    "technical_strength": {
        "description": "Technical analysis aggregate strength",
        "weights": {"passthrough_from_technical_engine": 1.0},
        "direction": "higher_is_better",
    },
    "options_sentiment": {
        "description": "Options flow and positioning sentiment",
        "weights": {"passthrough_from_options_engine": 1.0},
        "direction": "higher_is_better",
    },
    "short_opportunity": {
        "description": "Quality of short setup opportunity",
        "weights": {"passthrough_from_short_engine": 1.0},
        "direction": "higher_is_more_shortable",
    },
    "squeeze_risk": {
        "description": "Risk of short squeeze forcing cover",
        "weights": {"passthrough_from_short_engine": 1.0},
        "direction": "higher_is_more_dangerous_to_short",
    },
    "news_regime": {
        "description": "News and sentiment regime state",
        "weights": {"avg_sentiment": 0.40, "policy_risk": 0.20,
                    "world_risk": 0.20, "funding_news": 0.20},
        "direction": "higher_is_more_positive",
    },
    "forecast_confidence": {
        "description": "Ensemble forecast model confidence",
        "weights": {"passthrough_from_forecast_engine": 1.0},
        "direction": "higher_is_more_confident",
    },
    "relative_strength_spy": {
        "description": "UPST relative strength vs SPY",
        "weights": {"passthrough_from_spy_beta_engine": 1.0},
        "direction": "higher_is_outperforming",
    },
    "trade_quality": {
        "description": "Aggregate trade quality assessment",
        "weights": {"signal_agreement": 0.40, "avg_confidence": 0.30, "base": 0.30},
        "direction": "higher_is_better_trade",
    },
    "positioning_fragility": {
        "description": "How fragile the current positioning is",
        "weights": {"squeeze_risk": 0.30, "signal_disagreement": 0.30,
                    "stale_data_count": 0.20, "low_confidence": 0.20},
        "direction": "higher_is_more_fragile",
    },
    "composite_opportunity": {
        "description": "Master composite of all 14 sub-scores",
        "weights": COMPOSITE_WEIGHTS,
        "direction": "higher_is_better_opportunity",
    },
}

# ── News Intelligence ──
NEWS_CATEGORIES = [
    "earnings", "funding", "origination", "macro", "fed", "credit",
    "fintech", "regulatory", "world", "peer", "general", "leadership",
    "product", "partnership", "ir_release", "social", "analyst",
]

NEWS_SOURCE_TYPES = ["news", "social", "ir", "ceo", "sec", "analyst"]

# Sentiment keyword dictionaries for news scoring
NEWS_POSITIVE_KEYWORDS = [
    "beat", "beats", "exceeded", "record", "growth", "expand", "launch",
    "partnership", "upgrade", "bullish", "rally", "profit", "profitable",
    "revenue growth", "origination", "approval", "approved", "new product",
    "momentum", "outperform", "raised guidance", "strong", "accelerat",
    "milestone", "breakthrough", "innovative", "surpass", "upside",
]

NEWS_NEGATIVE_KEYWORDS = [
    "miss", "missed", "decline", "loss", "downgrade", "bearish", "sell",
    "concern", "risk", "lawsuit", "probe", "investigation", "delinquency",
    "default", "layoff", "cut", "warning", "weak", "slowdown", "headwind",
    "regulatory scrutiny", "black box", "uncertain", "volatile", "crash",
    "plunge", "short seller", "fraud", "overvalued", "bubble",
]

NEWS_UPST_KEYWORDS = [
    "upstart", "upst", "ai lending", "ai credit", "ai underwriting",
    "dave girouard", "paul gu", "sanjay datta",
]

CEO_POSITIVE_TONE_WORDS = [
    "excited", "incredible", "record", "milestone", "transformative",
    "accelerating", "confident", "optimistic", "proud", "thrilled",
]

CEO_CAUTIOUS_TONE_WORDS = [
    "cautious", "prudent", "careful", "measured", "conservative",
    "challenge", "headwind", "uncertain", "navigating",
]

# ── Alert Thresholds ──
ALERT_THRESHOLDS = {
    "iv_extreme_pct": 100,       # ATM IV > 100% = critical
    "iv_percentile_high": 90,    # IV percentile > 90th
    "pc_ratio_high": 2.0,        # Put/call ratio above this = elevated
    "pc_ratio_low": 0.4,         # Put/call ratio below this = complacent
    "squeeze_risk_high": 75,     # Squeeze score above this = critical
    "composite_high": 75,        # Composite above this = opportunity
    "composite_low": 25,         # Composite below this = unfavorable
    "drawdown_warning_pct": 30,  # Max drawdown above this = warning
    "borrow_cost_high_pct": 30,  # Cost to borrow above this = expensive
    "utilization_extreme_pct": 90,
    "si_change_spike_pct": 15,   # SI change above this = significant
    "funding_expiry_critical_months": 3,
    "funding_expiry_watch_months": 6,
    "concentration_risk_pct": 40,
    "hy_spread_stress_bps": 500,
    "origination_collapse_yoy_pct": -30,
    "forecast_confidence_low": 20,
    "beta_divergence_threshold": 0.5,
    "correlation_breakdown": 0.15,
}

# ── Scoring Engine Thresholds ──
# Funding benchmarks (what value = 100 score)
FUNDING_CAPACITY_BENCHMARK = 3.0        # $3B committed = 100
FUNDING_COVERAGE_BENCHMARK_MONTHS = 24  # 24 months = 100
FUNDING_PARTNER_BENCHMARK = 10          # 10 partners = 100
FUNDING_MATURITY_BENCHMARK_MONTHS = 36  # 36 months avg maturity = 100

# Origination scaling
ORIGINATION_GROWTH_NEUTRAL = 50         # Midpoint for QoQ/YoY growth mapping
ORIGINATION_PRODUCT_BENCHMARK = 4       # 4 products = 100

# Macro scaling
MACRO_FED_SCALING = 15                  # fed_funds * 15 (5% → 75 score)
MACRO_HY_SPREAD_NEUTRAL_BPS = 200      # Baseline HY spread
MACRO_HY_SPREAD_SCALING = 4            # (spread - 200) / 4
MACRO_UNEMPLOYMENT_SCALING = 15         # unemployment * 15
MACRO_DELINQUENCY_SCALING = 25          # delinquency * 25

# Valuation scaling
VALUATION_PS_MEDIAN_DEFAULT = 8.0       # Historical P/S median for UPST
VALUATION_PS_PEERS_SCALING = 8          # 100 - ps * 8
VALUATION_EV_REV_SCALING = 8            # 100 - ev/rev * 8
VALUATION_GROWTH_ADJ_SCALING = 15       # growth / ps * 15

# News scaling
NEWS_SENTIMENT_SCALING = 50             # sentiment * 50 → 0..100 mapping
NEWS_RISK_ADJUSTMENT = 10               # Points for policy/world/funding risk

# Trade quality thresholds
TRADE_QUALITY_CONFIDENCE_FLOOR = 0.5    # Min confidence to count in agreement
TRADE_QUALITY_BULLISH_THRESHOLD = 60    # Score > 60 = bullish signal
TRADE_QUALITY_BEARISH_THRESHOLD = 40    # Score < 40 = bearish signal
COMPOSITE_CONFIDENCE_FLOOR = 0.3        # Min confidence to include in composite

# Fragility scaling
FRAGILITY_STALE_PENALTY = 5             # Points per stale input (capped)
FRAGILITY_MAX_STALE_PENALTY = 40        # Max points from stale data
FRAGILITY_BASE = 20                     # Base fragility score

# ── Trade Decision Thresholds ──
TD_MIN_TRADE_QUALITY = 30               # Below this → no_trade
TD_MIN_SIGNAL_AGREEMENT = 30            # Below this → no_trade
TD_COMPOSITE_BULLISH = 65               # Above this + bullish signals → bullish
TD_COMPOSITE_BEARISH = 35               # Below this → bearish
TD_TECH_BUY_THRESHOLD = 70              # Technical > 70 → buy common stock
TD_OPTIONS_BUY_THRESHOLD = 65           # Options > 65 → buy calls
TD_SQUEEZE_OPTIONS_THRESHOLD = 70       # Squeeze > 70 → use options not stock
TD_SHORT_OPP_THRESHOLD = 65             # Short opp > 65 → direct short

# Sizing
TD_BASE_POSITION_PCT = 5.0             # 5% base allocation
TD_MIN_POSITION_PCT = 1.0              # Minimum position
TD_MAX_POSITION_PCT = 10.0             # Maximum position
TD_QUALITY_NORM = 60                   # Quality normalization divisor

# Regime multipliers for sizing
TD_REGIME_CRISIS = 0.4
TD_REGIME_HIGH_VOL = 0.6
TD_REGIME_BEAR = 0.7
TD_REGIME_BULL = 1.1

# ATR-based level multipliers
TD_ATR_TARGET_MULT = 3.0              # Target = price ± atr * 3
TD_ATR_STOP_MULT = 1.5                # Stop = price ∓ atr * 1.5
TD_ATR_NEUTRAL_MULT = 2.0             # Neutral hold levels

# Win probability
TD_WIN_PROB_MIN = 0.15
TD_WIN_PROB_MAX = 0.85
TD_COMPOSITE_PROB_SCALING = 200        # Composite-to-probability divisor
TD_AGREEMENT_BONUS_SCALING = 500
TD_QUALITY_BONUS_SCALING = 500
TD_FRAGILITY_PENALTY_SCALING = 500

# Confidence thresholds
TD_HIGH_AGREEMENT = 70
TD_HIGH_QUALITY = 60
TD_LOW_FRAGILITY = 40

# Fallback stop distance
TD_FALLBACK_STOP_PCT = 0.02           # 2% default stop

# ── Short Structure Decision Matrix ──
SHORT_STRUCTURE_MATRIX = {
    "low_iv_low_squeeze": "direct_short",
    "low_iv_high_squeeze": "put_debit_spread",
    "high_iv_low_squeeze": "bear_call_spread",
    "high_iv_high_squeeze": "no_short_trade",
    "event_risk": "put_debit_spread",
    "strong_downtrend": "direct_short",
}

# ── Regime Definitions ──
REGIME_TYPES = ["risk_on", "risk_off", "squeeze", "trend", "chop", "normal"]

# ── Bot Configuration ──
BOT_NAMES = [
    "price_action", "options_reaction", "squeeze",
    "funding_stress", "macro_shock", "strategy",
    "trade_decision", "regime",
]
