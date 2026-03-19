"""
Forecasting / Simulation / Monte Carlo Engine — Phase 5
Multi-model price forecasting with uncertainty quantification.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from backend.config.constants import MC_DEFAULT_PATHS, MC_DEFAULT_HORIZON_DAYS


@dataclass
class ForecastResult:
    """Multi-model forecast output."""
    ticker: str
    forecast_time: dt.datetime
    horizon_days: int
    model_name: str

    point_estimate: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    confidence_level: float = 0.80

    probability_up: float | None = None
    probability_down: float | None = None
    probability_flat: float | None = None  # within +/- 2%

    paths: np.ndarray | None = None  # MC paths if applicable
    percentiles: dict = field(default_factory=dict)  # 5, 10, 25, 50, 75, 90, 95

    regime_context: str = ""
    assumptions: dict = field(default_factory=dict)
    explanation: str = ""
    confidence_score: float = 50.0  # 0..100


@dataclass
class EnsembleForecast:
    """Combined forecast from multiple models."""
    individual_forecasts: list[ForecastResult] = field(default_factory=list)
    ensemble_point: float | None = None
    ensemble_lower: float | None = None
    ensemble_upper: float | None = None
    model_agreement: float = 0.0  # 0..1
    confidence_score: float = 50.0


class ForecastEngine:
    """Multi-model forecasting with Monte Carlo, mean-reversion, and momentum models."""

    def forecast(
        self,
        df: pd.DataFrame,
        ticker: str = "UPST",
        horizon_days: int = MC_DEFAULT_HORIZON_DAYS,
        n_paths: int = MC_DEFAULT_PATHS,
        spy_beta: float = 1.5,
        current_regime: str = "normal",
    ) -> EnsembleForecast:
        """Run all forecast models and combine into ensemble."""
        if df.empty or len(df) < 60:
            return EnsembleForecast(confidence_score=10.0)

        close = df["close"].astype(float)
        price = float(close.iloc[-1])
        returns = close.pct_change().dropna()
        now = dt.datetime.now(dt.timezone.utc)

        forecasts = []

        # Model 1: GBM Monte Carlo
        gbm = self._gbm_forecast(close, returns, price, horizon_days, n_paths, ticker, now)
        forecasts.append(gbm)

        # Model 2: Mean-Reversion
        mr = self._mean_reversion_forecast(close, returns, price, horizon_days, ticker, now)
        forecasts.append(mr)

        # Model 3: Momentum / Trend
        mom = self._momentum_forecast(close, returns, price, horizon_days, ticker, now)
        forecasts.append(mom)

        # Model 4: Regime-Conditional
        regime = self._regime_forecast(close, returns, price, horizon_days, current_regime, ticker, now)
        forecasts.append(regime)

        # ── Ensemble ──
        ensemble = self._build_ensemble(forecasts, price)
        return ensemble

    def _gbm_forecast(
        self, close, returns, price, horizon, n_paths, ticker, now,
    ) -> ForecastResult:
        """Geometric Brownian Motion with historical drift and volatility."""
        mu = float(returns.mean()) * 252
        sigma = float(returns.std()) * math.sqrt(252)
        dt_val = 1 / 252

        paths = np.zeros((n_paths, horizon + 1))
        paths[:, 0] = price

        for t in range(1, horizon + 1):
            z = np.random.standard_normal(n_paths)
            paths[:, t] = paths[:, t-1] * np.exp(
                (mu - 0.5 * sigma**2) * dt_val + sigma * math.sqrt(dt_val) * z
            )

        final = paths[:, -1]
        percentiles = {
            p: round(float(np.percentile(final, p)), 2)
            for p in [5, 10, 25, 50, 75, 90, 95]
        }

        return ForecastResult(
            ticker=ticker, forecast_time=now, horizon_days=horizon,
            model_name="gbm_monte_carlo",
            point_estimate=percentiles[50],
            lower_bound=percentiles[10],
            upper_bound=percentiles[90],
            probability_up=round(float(np.mean(final > price * 1.02)), 4),
            probability_down=round(float(np.mean(final < price * 0.98)), 4),
            probability_flat=round(float(np.mean((final >= price * 0.98) & (final <= price * 1.02))), 4),
            paths=paths,
            percentiles=percentiles,
            assumptions={"mu": round(mu, 4), "sigma": round(sigma, 4), "n_paths": n_paths},
            explanation=f"GBM with historical drift={mu:.2%}, vol={sigma:.2%}",
            confidence_score=55.0,
        )

    def _mean_reversion_forecast(
        self, close, returns, price, horizon, ticker, now,
    ) -> ForecastResult:
        """Ornstein-Uhlenbeck mean-reversion model."""
        log_prices = np.log(close.values)
        mean_log = float(np.mean(log_prices[-252:]))
        half_life = self._estimate_half_life(log_prices)
        if half_life is None or half_life <= 0:
            half_life = 63  # Default 3-month half-life

        kappa = math.log(2) / half_life
        sigma = float(returns.std()) * math.sqrt(252)

        # Projected mean-reversion path
        target = math.exp(mean_log)
        projected = price + (target - price) * (1 - math.exp(-kappa * horizon / 252))

        # Uncertainty band
        std_dev = sigma * math.sqrt((1 - math.exp(-2 * kappa * horizon / 252)) / (2 * kappa)) * price
        lower = round(projected - 1.645 * std_dev, 2)
        upper = round(projected + 1.645 * std_dev, 2)

        prob_up = 1 - sp_stats.norm.cdf(price * 1.02, loc=projected, scale=max(std_dev, 0.01))
        prob_down = sp_stats.norm.cdf(price * 0.98, loc=projected, scale=max(std_dev, 0.01))

        return ForecastResult(
            ticker=ticker, forecast_time=now, horizon_days=horizon,
            model_name="mean_reversion_ou",
            point_estimate=round(projected, 2),
            lower_bound=lower, upper_bound=upper,
            probability_up=round(float(prob_up), 4),
            probability_down=round(float(prob_down), 4),
            probability_flat=round(float(1 - prob_up - prob_down), 4),
            assumptions={"half_life": round(half_life, 1), "kappa": round(kappa, 4),
                          "target_price": round(target, 2)},
            explanation=f"OU mean-reversion, half-life={half_life:.0f} days, target=${target:.2f}",
            confidence_score=50.0,
        )

    def _momentum_forecast(
        self, close, returns, price, horizon, ticker, now,
    ) -> ForecastResult:
        """Momentum / trend-following forecast."""
        # Use 20-day and 50-day momentum
        mom_20 = float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) > 21 else 0
        mom_50 = float(close.iloc[-1] / close.iloc[-51] - 1) if len(close) > 51 else 0
        avg_mom = (mom_20 * 0.6 + mom_50 * 0.4)

        # Project momentum forward with decay
        decay = 0.95 ** (horizon / 21)
        projected_return = avg_mom * decay * (horizon / 21)
        projected = round(price * (1 + projected_return), 2)

        sigma = float(returns.std()) * math.sqrt(horizon / 252)
        lower = round(projected * (1 - 1.645 * sigma), 2)
        upper = round(projected * (1 + 1.645 * sigma), 2)

        return ForecastResult(
            ticker=ticker, forecast_time=now, horizon_days=horizon,
            model_name="momentum_trend",
            point_estimate=projected,
            lower_bound=lower, upper_bound=upper,
            probability_up=round(0.5 + avg_mom * 2, 4) if avg_mom > 0 else round(max(0.1, 0.5 + avg_mom * 2), 4),
            probability_down=round(0.5 - avg_mom * 2, 4) if avg_mom > 0 else round(min(0.9, 0.5 - avg_mom * 2), 4),
            assumptions={"mom_20d": round(mom_20, 4), "mom_50d": round(mom_50, 4),
                          "decay": round(decay, 4)},
            explanation=f"Momentum model: 20d={mom_20:.2%}, 50d={mom_50:.2%}",
            confidence_score=45.0,
        )

    def _regime_forecast(
        self, close, returns, price, horizon, regime, ticker, now,
    ) -> ForecastResult:
        """Regime-conditional forecast (adjusts drift/vol for current regime)."""
        base_mu = float(returns.mean()) * 252
        base_sigma = float(returns.std()) * math.sqrt(252)

        regime_adjustments = {
            "risk_on": (base_mu * 1.3, base_sigma * 0.85),
            "risk_off": (base_mu * 0.5 - 0.10, base_sigma * 1.3),
            "squeeze": (base_mu + 0.20, base_sigma * 1.5),
            "compressed": (base_mu * 0.7, base_sigma * 0.6),
            "normal": (base_mu, base_sigma),
        }
        mu, sigma = regime_adjustments.get(regime, (base_mu, base_sigma))

        # Simple forward projection
        projected = round(price * math.exp(mu * horizon / 252), 2)
        std = sigma * math.sqrt(horizon / 252) * price
        lower = round(projected - 1.645 * std, 2)
        upper = round(projected + 1.645 * std, 2)

        return ForecastResult(
            ticker=ticker, forecast_time=now, horizon_days=horizon,
            model_name=f"regime_{regime}",
            point_estimate=projected,
            lower_bound=lower, upper_bound=upper,
            regime_context=regime,
            assumptions={"adj_mu": round(mu, 4), "adj_sigma": round(sigma, 4), "regime": regime},
            explanation=f"Regime-conditional ({regime}): μ={mu:.2%}, σ={sigma:.2%}",
            confidence_score=40.0,
        )

    def _estimate_half_life(self, log_prices: np.ndarray) -> float | None:
        """Estimate mean-reversion half-life via ADF-like regression."""
        if len(log_prices) < 30:
            return None
        y = np.diff(log_prices)
        x = log_prices[:-1] - np.mean(log_prices)
        if np.std(x) == 0:
            return None
        slope, _, _, _, _ = sp_stats.linregress(x, y)
        if slope >= 0:
            return None  # No mean reversion detected
        return -math.log(2) / slope

    def _build_ensemble(self, forecasts: list[ForecastResult], price: float) -> EnsembleForecast:
        """Weight-average individual forecasts."""
        if not forecasts:
            return EnsembleForecast()

        # Weight by confidence
        total_weight = sum(f.confidence_score for f in forecasts)
        if total_weight == 0:
            total_weight = 1

        ensemble_point = sum(
            (f.point_estimate or price) * f.confidence_score for f in forecasts
        ) / total_weight

        ensemble_lower = sum(
            (f.lower_bound or price * 0.8) * f.confidence_score for f in forecasts
        ) / total_weight

        ensemble_upper = sum(
            (f.upper_bound or price * 1.2) * f.confidence_score for f in forecasts
        ) / total_weight

        # Model agreement: how close are point estimates?
        points = [f.point_estimate for f in forecasts if f.point_estimate]
        if len(points) > 1:
            std_points = np.std(points)
            agreement = max(0, 1 - std_points / price * 10)
        else:
            agreement = 0.5

        confidence = min(100, agreement * 50 + sum(f.confidence_score for f in forecasts) / len(forecasts))

        return EnsembleForecast(
            individual_forecasts=forecasts,
            ensemble_point=round(ensemble_point, 2),
            ensemble_lower=round(ensemble_lower, 2),
            ensemble_upper=round(ensemble_upper, 2),
            model_agreement=round(agreement, 4),
            confidence_score=round(confidence, 2),
        )
