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
