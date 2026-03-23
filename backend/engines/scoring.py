"""
Scoring Engine — All 15 Mandatory Scores
Each score: formula, weights, component breakdown, confidence/freshness flags.
"""

from __future__ import annotations

import datetime as dt
import json
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
            return ScoreResult(name="funding_strength", value=50.0,
                               explanation="No funding data available", confidence=0.3)

        components = {}
        weights = {"capacity": 0.25, "coverage": 0.20, "diversification": 0.15,
                    "maturity": 0.15, "renewal": 0.15, "covenants": 0.10}

        components["capacity"] = min(100, max(0, data.get("total_committed", 0) / FUNDING_CAPACITY_BENCHMARK * 100))
        components["coverage"] = min(100, max(0, data.get("months_coverage", 0) / FUNDING_COVERAGE_BENCHMARK_MONTHS * 100))
        components["diversification"] = min(100, max(0, data.get("partner_count", 0) / FUNDING_PARTNER_BENCHMARK * 100))
        components["maturity"] = min(100, max(0, data.get("avg_months_to_maturity", 0) / FUNDING_MATURITY_BENCHMARK_MONTHS * 100))
        # Renewal probability: accept both decimal (0-1) and percentage (0-100)
        renewal = data.get("avg_renewal_prob", 0.5)
        if renewal > 1.0:
            renewal = renewal / 100.0  # Convert percentage to decimal
        components["renewal"] = min(100, max(0, renewal * 100))
        components["covenants"] = 100 if not data.get("has_covenant_issues") else 30

        value = sum(components[k] * weights[k] for k in weights)
        return ScoreResult(
            name="funding_strength", value=round(max(0, min(100, value)), 2),
            components=components, weights=weights,
            explanation=f"Funding strength based on {len(weights)} factors",
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
            return ScoreResult(name="origination_momentum", value=50.0, confidence=0.3)

        components = {}
        weights = {"qoq": 0.30, "yoy": 0.25, "volume": 0.20, "accel": 0.15, "diversification": 0.10}

        qoq = max(-1.0, min(1.0, data.get("qoq_growth", 0)))  # Clamp to ±100%
        yoy = max(-1.0, min(1.0, data.get("yoy_growth", 0)))
        components["qoq"] = max(0, min(100, ORIGINATION_GROWTH_NEUTRAL + qoq * 100))
        components["yoy"] = max(0, min(100, ORIGINATION_GROWTH_NEUTRAL + yoy * 100))
        components["volume"] = min(100, max(0, data.get("volume_index", 50)))
        components["accel"] = 70 if data.get("accelerating") else 30
        components["diversification"] = min(100, max(0, data.get("product_count", 1) / ORIGINATION_PRODUCT_BENCHMARK * 100))

        value = sum(components[k] * weights[k] for k in weights)
        return ScoreResult(
            name="origination_momentum", value=round(max(0, min(100, value)), 2),
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
            return ScoreResult(name="macro_pressure", value=50.0, confidence=0.3)

        components = {}
        weights = {"fed": 0.20, "curve": 0.15, "hy": 0.20,
                    "unemp": 0.15, "recession": 0.15, "lending": 0.15}

        fed = max(0, min(10, data.get("fed_funds", 5.0)))  # Clamp 0-10%
        components["fed"] = min(100, fed * MACRO_FED_SCALING)
        components["curve"] = 80 if data.get("yield_curve_inverted") else 30
        hy_spread = max(0, min(2000, data.get("hy_spread", 350)))  # Clamp 0-2000bps
        components["hy"] = min(100, max(0, (hy_spread - MACRO_HY_SPREAD_NEUTRAL_BPS) / MACRO_HY_SPREAD_SCALING))
        unemp = max(0, min(20, data.get("unemployment", 4.0)))  # Clamp 0-20%
        components["unemp"] = min(100, unemp * MACRO_UNEMPLOYMENT_SCALING)
        components["recession"] = min(100, max(0, data.get("recession_prob", 20)))
        components["lending"] = min(100, max(0, data.get("lending_standards", 0) + 50))

        value = sum(components[k] * weights[k] for k in weights)
        return ScoreResult(
            name="macro_pressure", value=round(max(0, min(100, value)), 2),
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
            return ScoreResult(name="credit_stress", value=50.0, confidence=0.3)

        components = {}
        weights = {"delinquency": 0.30, "hy": 0.25, "lending": 0.25, "credit": 0.20}

        delinq = max(0, min(10, data.get("delinquency_rate", 2.5)))  # Clamp 0-10%
        components["delinquency"] = min(100, delinq * MACRO_DELINQUENCY_SCALING)
        hy_spread = max(0, min(2000, data.get("hy_spread", 350)))
        components["hy"] = min(100, max(0, (hy_spread - MACRO_HY_SPREAD_NEUTRAL_BPS) / MACRO_HY_SPREAD_SCALING))
        components["lending"] = min(100, max(0, data.get("lending_standards", 0) + 50))
        components["credit"] = max(0, 100 - max(0, min(20, data.get("consumer_credit_growth", 5))) * 10)

        value = sum(components[k] * weights[k] for k in weights)
        return ScoreResult(
            name="credit_stress", value=round(max(0, min(100, value)), 2),
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
            return ScoreResult(name="valuation_attractiveness", value=50.0, confidence=0.3)

        components = {}
        weights = {"ps_history": 0.25, "ps_peers": 0.20, "ev_rev": 0.15,
                    "growth_adj": 0.20, "fcf": 0.10, "fair_value": 0.10}

        ps = max(0.1, data.get("price_to_sales", 5.0))  # Floor at 0.1 to avoid extreme ratios
        ps_hist_median = max(0.1, data.get("ps_median_3y", VALUATION_PS_MEDIAN_DEFAULT))
        components["ps_history"] = min(100, max(0, (ps_hist_median - ps) / ps_hist_median * 100 + 50))
        components["ps_peers"] = min(100, max(0, 100 - ps * VALUATION_PS_PEERS_SCALING))
        ev_rev = max(0, data.get("ev_revenue", 6))
        components["ev_rev"] = min(100, max(0, 100 - ev_rev * VALUATION_EV_REV_SCALING))
        growth = max(0, min(200, data.get("growth_rate", 20)))  # Clamp growth rate
        components["growth_adj"] = min(100, max(0, growth / ps * VALUATION_GROWTH_ADJ_SCALING))
        components["fcf"] = min(100, max(0, data.get("fcf_yield", 0) * 10 + 50))
        components["fair_value"] = min(100, max(0, data.get("upside_to_fair", 0) + 50))

        value = sum(components[k] * weights[k] for k in weights)
        return ScoreResult(
            name="valuation_attractiveness", value=round(max(0, min(100, value)), 2),
            components=components, weights=weights,
        )

    def _technical_strength(self, data: dict | None) -> ScoreResult:
        """Passthrough from TechnicalEngine score."""
        if not data:
            return ScoreResult(name="technical_strength", value=50.0, confidence=0.3)
        return ScoreResult(
            name="technical_strength",
            value=max(0, min(100, data.get("technical_strength_score", 50.0))),
            explanation="Computed by TechnicalEngine",
        )

    def _options_sentiment(self, data: dict | None) -> ScoreResult:
        if not data:
            return ScoreResult(name="options_sentiment", value=50.0, confidence=0.3)
        return ScoreResult(
            name="options_sentiment",
            value=max(0, min(100, data.get("options_sentiment_score", 50.0))),
            explanation="Computed by OptionsEngine",
        )

    def _short_opportunity(self, data: dict | None) -> ScoreResult:
        if not data:
            return ScoreResult(name="short_opportunity", value=50.0, confidence=0.3)
        return ScoreResult(
            name="short_opportunity",
            value=max(0, min(100, data.get("short_opportunity_score", 50.0))),
        )

    def _squeeze_risk(self, data: dict | None) -> ScoreResult:
        if not data:
            return ScoreResult(name="squeeze_risk", value=50.0, confidence=0.3)
        return ScoreResult(
            name="squeeze_risk",
            value=max(0, min(100, data.get("squeeze_risk_score", 50.0))),
        )

    def _news_regime(self, data: dict | None) -> ScoreResult:
        """
        News/Regime Score (0-100): HIGH = POSITIVE sentiment.
        - Avg sentiment: 40%
        - Policy risk: 20%
        - World risk: 20%
        - Funding news: 20%
        """
        if not data:
            return ScoreResult(name="news_regime", value=50.0, confidence=0.3)

        avg_sent = max(-1, min(1, data.get("avg_sentiment", 0)))  # Clamp to [-1, 1]
        score = 50 + avg_sent * NEWS_SENTIMENT_SCALING
        if data.get("policy_risk"):
            score -= NEWS_RISK_ADJUSTMENT
        if data.get("world_risk"):
            score -= NEWS_RISK_ADJUSTMENT
        if data.get("positive_funding_news"):
            score += NEWS_RISK_ADJUSTMENT
        return ScoreResult(name="news_regime", value=round(max(0, min(100, score)), 2))

    def _forecast_confidence(self, data: dict | None) -> ScoreResult:
        if not data:
            return ScoreResult(name="forecast_confidence", value=50.0, confidence=0.3)
        return ScoreResult(
            name="forecast_confidence",
            value=max(0, min(100, data.get("confidence_score", 50.0))),
        )

    def _relative_strength_spy(self, data: dict | None) -> ScoreResult:
        if not data:
            return ScoreResult(name="relative_strength_spy", value=50.0, confidence=0.3)
        return ScoreResult(
            name="relative_strength_spy",
            value=max(0, min(100, data.get("relative_strength_score", 50.0))),
        )

    def _trade_quality(self, scores: dict) -> ScoreResult:
        """
        Trade Quality Score (0-100):
        - Signal agreement across engines: 40%
        - Confidence level: 30%
        - Low fragility: 30%
        """
        available = [s.value for s in scores.values() if s.confidence > TRADE_QUALITY_CONFIDENCE_FLOOR]
        if not available:
            return ScoreResult(name="trade_quality", value=50.0, confidence=0.3)

        # How much do signals agree on direction?
        bullish = sum(1 for v in available if v > TRADE_QUALITY_BULLISH_THRESHOLD)
        bearish = sum(1 for v in available if v < TRADE_QUALITY_BEARISH_THRESHOLD)
        total = len(available)
        agreement = max(bullish, bearish) / total if total > 0 else 0.5
        avg_confidence = sum(s.confidence for s in scores.values()) / len(scores) if scores else 0.5

        # agreement (0-1) contributes up to 40 pts, confidence (0-1) up to 30 pts, base 30
        score = agreement * 40 + avg_confidence * 30 + 30
        return ScoreResult(
            name="trade_quality",
            value=round(max(0, min(100, score)), 2),
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
        low_conf_avg = sum(1 for s in scores.values() if s.confidence < 0.5) / max(1, len(scores)) * 100

        # Cap stale data penalty to prevent unbounded growth
        stale_penalty = min(FRAGILITY_MAX_STALE_PENALTY, stale_count * FRAGILITY_STALE_PENALTY)

        score = (squeeze * 0.30
                 + (100 - agreement) * 0.30
                 + stale_penalty * 0.20
                 + low_conf_avg * 0.20)
        return ScoreResult(
            name="positioning_fragility",
            value=round(max(0, min(100, score)), 2),
            components={
                "squeeze_contribution": round(squeeze * 0.30, 2),
                "disagreement_contribution": round((100 - agreement) * 0.30, 2),
                "stale_data_penalty": round(stale_penalty, 2),
                "low_confidence_pct": round(low_conf_avg, 2),
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
                    val = 100 - val  # Invert for negative-weight scores
                    weight = abs(weight)
                components[name] = round(val * weight, 4)
                total += val * weight
                weight_sum += weight

        composite = total / weight_sum if weight_sum > 0 else 50.0
        return ScoreResult(
            name="composite_opportunity",
            value=round(max(0, min(100, composite)), 2),
            components=components,
            weights=dict(COMPOSITE_WEIGHTS),
            explanation="Weighted composite of all 14 component scores",
        )
