"""
Scoring Engine — All 15 Mandatory Scores
Each score: formula, weights, component breakdown, confidence/freshness flags.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from backend.config.constants import (
    COMPOSITE_WEIGHTS,
    FUNDING_CAPACITY_BENCHMARK, FUNDING_COVERAGE_BENCHMARK_MONTHS,
    FUNDING_PARTNER_BENCHMARK, FUNDING_MATURITY_BENCHMARK_MONTHS,
    ORIGINATION_GROWTH_NEUTRAL, ORIGINATION_PRODUCT_BENCHMARK,
    MACRO_FED_SCALING, MACRO_HY_SPREAD_NEUTRAL_BPS, MACRO_HY_SPREAD_SCALING,
    MACRO_UNEMPLOYMENT_SCALING, MACRO_DELINQUENCY_SCALING,
    VALUATION_PS_MEDIAN_DEFAULT, VALUATION_PS_PEERS_SCALING,
    VALUATION_EV_REV_SCALING, VALUATION_GROWTH_ADJ_SCALING,
    NEWS_SENTIMENT_SCALING, NEWS_RISK_ADJUSTMENT,
    TRADE_QUALITY_CONFIDENCE_FLOOR, TRADE_QUALITY_BULLISH_THRESHOLD,
    TRADE_QUALITY_BEARISH_THRESHOLD, COMPOSITE_CONFIDENCE_FLOOR,
    FRAGILITY_STALE_PENALTY, FRAGILITY_MAX_STALE_PENALTY, FRAGILITY_BASE,
)


def _clamp(value: float, lo: float = 0, hi: float = 100) -> float:
    """Clamp a value to [lo, hi]."""
    return max(lo, min(hi, value))


@dataclass
class ScoreResult:
    name: str
    value: float  # 0..100
    components: dict = field(default_factory=dict)
    weights: dict = field(default_factory=dict)
    freshness: dict = field(default_factory=dict)  # component -> seconds since update
    confidence: float = 1.0
    explanation: str = ""
    stale_inputs: list[str] = field(default_factory=list)


class ScoringEngine:
    """Computes all 15 mandatory scores from engine outputs."""

    @staticmethod
    def _no_data(name: str) -> ScoreResult:
        """Default result when input data is missing."""
        return ScoreResult(name=name, value=50.0, confidence=0.3)

    @staticmethod
    def _passthrough(name: str, data: dict | None, key: str) -> ScoreResult:
        """Passthrough score from another engine."""
        if not data:
            return ScoreResult(name=name, value=50.0, confidence=0.3)
        return ScoreResult(name=name, value=_clamp(data.get(key, 50.0)))

    @staticmethod
    def _hy_spread_score(data: dict) -> float:
        """HY spread component score (shared by macro_pressure and credit_stress)."""
        hy_spread = _clamp(data.get("hy_spread", 350), 0, 2000)
        return _clamp((hy_spread - MACRO_HY_SPREAD_NEUTRAL_BPS) / MACRO_HY_SPREAD_SCALING)

    @staticmethod
    def _lending_score(data: dict) -> float:
        """Lending standards component score (shared by macro_pressure and credit_stress)."""
        return _clamp(data.get("lending_standards", 0) + 50)

    def compute_all(
        self,
        technical: dict | None = None,
        options: dict | None = None,
        short: dict | None = None,
        funding: dict | None = None,
        origination: dict | None = None,
        macro: dict | None = None,
        valuation: dict | None = None,
        news: dict | None = None,
        spy_rel: dict | None = None,
        forecast: dict | None = None,
    ) -> dict[str, ScoreResult]:
        """Returns all 15 scores keyed by name."""
        scores = {}
        scores["funding_strength"] = self._funding_strength(funding)
        scores["origination_momentum"] = self._origination_momentum(origination)
        scores["macro_pressure"] = self._macro_pressure(macro)
        scores["credit_stress"] = self._credit_stress(macro)
        scores["valuation_attractiveness"] = self._valuation_attractiveness(valuation)
        scores["technical_strength"] = self._technical_strength(technical)
        scores["options_sentiment"] = self._options_sentiment(options)
        scores["short_opportunity"] = self._short_opportunity(short)
        scores["squeeze_risk"] = self._squeeze_risk(short)
        scores["news_regime"] = self._news_regime(news)
        scores["forecast_confidence"] = self._forecast_confidence(forecast)
        scores["relative_strength_spy"] = self._relative_strength_spy(spy_rel)
        scores["trade_quality"] = self._trade_quality(scores)
        scores["positioning_fragility"] = self._positioning_fragility(scores)
        scores["composite_opportunity"] = self._composite(scores)
        return scores

    # ── Individual Score Implementations ──

    def _funding_strength(self, data: dict | None) -> ScoreResult:
        """
        Funding Strength Score (0-100):
        - Total committed capacity: 25%
        - Months of funding coverage: 20%
        - Partner diversification: 15%
        - Maturity profile: 15%
        - Renewal probability: 15%
        - No covenant/waiver issues: 10%
        """
        if not data:
            return self._no_data("funding_strength")

        components = {}
        weights = {"capacity": 0.25, "coverage": 0.20, "diversification": 0.15,
                    "maturity": 0.15, "renewal": 0.15, "covenants": 0.10}

        components["capacity"] = _clamp(data.get("total_committed", 0) / FUNDING_CAPACITY_BENCHMARK * 100)
        components["coverage"] = _clamp(data.get("months_coverage", 0) / FUNDING_COVERAGE_BENCHMARK_MONTHS * 100)
        components["diversification"] = _clamp(data.get("partner_count", 0) / FUNDING_PARTNER_BENCHMARK * 100)
        components["maturity"] = _clamp(data.get("avg_months_to_maturity", 0) / FUNDING_MATURITY_BENCHMARK_MONTHS * 100)
        # Accept both decimal (0-1) and percentage (0-100) for renewal probability
        renewal = data.get("avg_renewal_prob", 0.5)
        if renewal > 1.0:
            renewal = renewal / 100.0
        components["renewal"] = _clamp(renewal * 100)
        components["covenants"] = 100 if not data.get("has_covenant_issues") else 30

        value = sum(components[k] * weights[k] for k in weights)
        return ScoreResult(
            name="funding_strength", value=round(_clamp(value), 2),
            components=components, weights=weights,
        )

    def _origination_momentum(self, data: dict | None) -> ScoreResult:
        """
        Origination Momentum Score (0-100):
        - QoQ growth: 30%
        - YoY growth: 25%
        - Volume level: 20%
        - Acceleration: 15%
        - Product diversification: 10%
        """
        if not data:
            return self._no_data("origination_momentum")

        components = {}
        weights = {"qoq": 0.30, "yoy": 0.25, "volume": 0.20, "accel": 0.15, "diversification": 0.10}

        qoq = _clamp(data.get("qoq_growth", 0), -1.0, 1.0)
        yoy = _clamp(data.get("yoy_growth", 0), -1.0, 1.0)
        components["qoq"] = _clamp(ORIGINATION_GROWTH_NEUTRAL + qoq * 100)
        components["yoy"] = _clamp(ORIGINATION_GROWTH_NEUTRAL + yoy * 100)
        components["volume"] = _clamp(data.get("volume_index", 50))
        components["accel"] = 70 if data.get("accelerating") else 30
        components["diversification"] = _clamp(data.get("product_count", 1) / ORIGINATION_PRODUCT_BENCHMARK * 100)

        value = sum(components[k] * weights[k] for k in weights)
        return ScoreResult(
            name="origination_momentum", value=round(_clamp(value), 2),
            components=components, weights=weights,
        )

    def _macro_pressure(self, data: dict | None) -> ScoreResult:
        """
        Macro Pressure Score (0-100): HIGH = MORE PRESSURE (bearish).
        - Fed Funds level: 20%
        - Yield curve: 15%
        - HY spreads: 20%
        - Unemployment trend: 15%
        - Recession probability: 15%
        - Lending standards: 15%
        """
        if not data:
            return self._no_data("macro_pressure")

        components = {}
        weights = {"fed": 0.20, "curve": 0.15, "hy": 0.20,
                    "unemp": 0.15, "recession": 0.15, "lending": 0.15}

        fed = _clamp(data.get("fed_funds", 5.0), 0, 10)
        components["fed"] = _clamp(fed * MACRO_FED_SCALING)
        components["curve"] = 80 if data.get("yield_curve_inverted") else 30
        components["hy"] = self._hy_spread_score(data)
        unemp = _clamp(data.get("unemployment", 4.0), 0, 20)
        components["unemp"] = _clamp(unemp * MACRO_UNEMPLOYMENT_SCALING)
        components["recession"] = _clamp(data.get("recession_prob", 20))
        components["lending"] = self._lending_score(data)

        value = sum(components[k] * weights[k] for k in weights)
        return ScoreResult(
            name="macro_pressure", value=round(_clamp(value), 2),
            components=components, weights=weights,
        )

    def _credit_stress(self, data: dict | None) -> ScoreResult:
        """
        Credit Stress Score (0-100): HIGH = MORE STRESS.
        - Consumer delinquency: 30%
        - HY spread: 25%
        - Lending standards tightening: 25%
        - Consumer credit growth: 20%
        """
        if not data:
            return self._no_data("credit_stress")

        components = {}
        weights = {"delinquency": 0.30, "hy": 0.25, "lending": 0.25, "credit": 0.20}

        delinq = _clamp(data.get("delinquency_rate", 2.5), 0, 10)
        components["delinquency"] = _clamp(delinq * MACRO_DELINQUENCY_SCALING)
        components["hy"] = self._hy_spread_score(data)
        components["lending"] = self._lending_score(data)
        components["credit"] = _clamp(100 - _clamp(data.get("consumer_credit_growth", 5), 0, 20) * 10)

        value = sum(components[k] * weights[k] for k in weights)
        return ScoreResult(
            name="credit_stress", value=round(_clamp(value), 2),
            components=components, weights=weights,
        )

    def _valuation_attractiveness(self, data: dict | None) -> ScoreResult:
        """
        Valuation Attractiveness Score (0-100): HIGH = CHEAP/ATTRACTIVE.
        - P/S vs history: 25%
        - P/S vs peers: 20%
        - EV/Revenue: 15%
        - Growth-adjusted (PEG-like): 20%
        - FCF yield: 10%
        - Distance from fair value: 10%
        """
        if not data:
            return self._no_data("valuation_attractiveness")

        components = {}
        weights = {"ps_history": 0.25, "ps_peers": 0.20, "ev_rev": 0.15,
                    "growth_adj": 0.20, "fcf": 0.10, "fair_value": 0.10}

        ps = max(0.1, data.get("price_to_sales", 5.0))
        ps_hist_median = max(0.1, data.get("ps_median_3y", VALUATION_PS_MEDIAN_DEFAULT))
        components["ps_history"] = _clamp((ps_hist_median - ps) / ps_hist_median * 100 + 50)
        components["ps_peers"] = _clamp(100 - ps * VALUATION_PS_PEERS_SCALING)
        ev_rev = max(0, data.get("ev_revenue", 6))
        components["ev_rev"] = _clamp(100 - ev_rev * VALUATION_EV_REV_SCALING)
        growth = _clamp(data.get("growth_rate", 20), 0, 200)
        components["growth_adj"] = _clamp(growth / ps * VALUATION_GROWTH_ADJ_SCALING)
        components["fcf"] = _clamp(data.get("fcf_yield", 0) * 10 + 50)
        components["fair_value"] = _clamp(data.get("upside_to_fair", 0) + 50)

        value = sum(components[k] * weights[k] for k in weights)
        return ScoreResult(
            name="valuation_attractiveness", value=round(_clamp(value), 2),
            components=components, weights=weights,
        )

    def _technical_strength(self, data: dict | None) -> ScoreResult:
        return self._passthrough("technical_strength", data, "technical_strength_score")

    def _options_sentiment(self, data: dict | None) -> ScoreResult:
        return self._passthrough("options_sentiment", data, "options_sentiment_score")

    def _short_opportunity(self, data: dict | None) -> ScoreResult:
        return self._passthrough("short_opportunity", data, "short_opportunity_score")

    def _squeeze_risk(self, data: dict | None) -> ScoreResult:
        return self._passthrough("squeeze_risk", data, "squeeze_risk_score")

    def _news_regime(self, data: dict | None) -> ScoreResult:
        """
        News/Regime Score (0-100): HIGH = POSITIVE sentiment.
        - Avg sentiment: 40%
        - Policy risk: 20%
        - World risk: 20%
        - Funding news: 20%
        """
        if not data:
            return self._no_data("news_regime")

        avg_sent = _clamp(data.get("avg_sentiment", 0), -1, 1)
        score = 50 + avg_sent * NEWS_SENTIMENT_SCALING
        if data.get("policy_risk"):
            score -= NEWS_RISK_ADJUSTMENT
        if data.get("world_risk"):
            score -= NEWS_RISK_ADJUSTMENT
        if data.get("positive_funding_news"):
            score += NEWS_RISK_ADJUSTMENT
        return ScoreResult(name="news_regime", value=round(_clamp(score), 2))

    def _forecast_confidence(self, data: dict | None) -> ScoreResult:
        return self._passthrough("forecast_confidence", data, "confidence_score")

    def _relative_strength_spy(self, data: dict | None) -> ScoreResult:
        return self._passthrough("relative_strength_spy", data, "relative_strength_score")

    def _trade_quality(self, scores: dict) -> ScoreResult:
        """
        Trade Quality Score (0-100):
        - Signal agreement across engines: 40%
        - Confidence level: 30%
        - Low fragility: 30%
        """
        available = [s.value for s in scores.values() if s.confidence > TRADE_QUALITY_CONFIDENCE_FLOOR]
        if not available:
            return self._no_data("trade_quality")

        bullish = sum(1 for v in available if v > TRADE_QUALITY_BULLISH_THRESHOLD)
        bearish = sum(1 for v in available if v < TRADE_QUALITY_BEARISH_THRESHOLD)
        total = len(available)
        agreement = max(bullish, bearish) / total if total > 0 else 0.5
        avg_confidence = sum(s.confidence for s in scores.values()) / len(scores) if scores else 0.5

        score = agreement * 40 + avg_confidence * 30 + 30
        return ScoreResult(
            name="trade_quality",
            value=round(_clamp(score), 2),
            components={"agreement": round(agreement * 100, 2), "avg_confidence": round(avg_confidence * 100, 2)},
        )

    def _positioning_fragility(self, scores: dict) -> ScoreResult:
        """
        Positioning Fragility Score (0-100): HIGH = FRAGILE.
        - Squeeze risk: 30%
        - Signal disagreement: 30%
        - Stale data count: 20% (capped)
        - Low confidence: 20%
        """
        squeeze = scores.get("squeeze_risk", ScoreResult(name="", value=50)).value
        trade_q = scores.get("trade_quality", ScoreResult(name="", value=50))
        agreement = trade_q.components.get("agreement", 50)
        stale_count = sum(1 for s in scores.values() if s.confidence < 0.5)
        low_conf_pct = stale_count / max(1, len(scores)) * 100  # Reuse stale_count

        stale_penalty = min(FRAGILITY_MAX_STALE_PENALTY, stale_count * FRAGILITY_STALE_PENALTY)

        score = (squeeze * 0.30
                 + (100 - agreement) * 0.30
                 + stale_penalty * 0.20
                 + low_conf_pct * 0.20)
        return ScoreResult(
            name="positioning_fragility",
            value=round(_clamp(score), 2),
            components={
                "squeeze_contribution": round(squeeze * 0.30, 2),
                "disagreement_contribution": round((100 - agreement) * 0.30, 2),
                "stale_data_penalty": round(stale_penalty, 2),
                "low_confidence_pct": round(low_conf_pct, 2),
            },
        )

    def _composite(self, scores: dict) -> ScoreResult:
        """
        Composite Opportunity Score — weighted combination of all scores.
        Weights from COMPOSITE_WEIGHTS in constants.
        Negative weights mean the score HURTS the composite when high.
        """
        components = {}
        total = 0.0
        weight_sum = 0.0

        for name, weight in COMPOSITE_WEIGHTS.items():
            sr = scores.get(name)
            if sr and sr.confidence > COMPOSITE_CONFIDENCE_FLOOR:
                val = sr.value
                if weight < 0:
                    val = 100 - val
                    weight = abs(weight)
                components[name] = round(val * weight, 4)
                total += val * weight
                weight_sum += weight

        composite = total / weight_sum if weight_sum > 0 else 50.0
        return ScoreResult(
            name="composite_opportunity",
            value=round(_clamp(composite), 2),
            components=components,
            weights=dict(COMPOSITE_WEIGHTS),
        )
