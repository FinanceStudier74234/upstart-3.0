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

        # Model 5: GARCH-based volatility forecast
        garch_fc = self._garch_forecast(returns, price, horizon_days, ticker, now)
        if garch_fc:
            forecasts.append(garch_fc)

        # Model 6: ARIMA-GARCH (if available)
        arima_fc = self._arima_forecast(returns, price, horizon_days, ticker, now)
        if arima_fc:
            forecasts.append(arima_fc)

        # ── Ensemble ──
        ensemble = self._build_ensemble(forecasts, price)
        return ensemble

    def _gbm_forecast(
        self, close, returns, price, horizon, n_paths, ticker, now,
    ) -> ForecastResult:
        """Geometric Brownian Motion with historical drift and volatility."""
        mu_raw = returns.mean()
        sigma_raw = returns.std()
        # Guard against NaN from empty/constant return series
        if np.isnan(mu_raw) or np.isnan(sigma_raw) or sigma_raw <= 0:
            return ForecastResult(
                ticker=ticker, forecast_time=now, horizon_days=horizon,
                model_name="gbm_monte_carlo", point_estimate=price,
                lower_bound=price * 0.8, upper_bound=price * 1.2,
                explanation="Insufficient return variance for GBM",
                confidence_score=10.0,
            )
        mu = float(mu_raw) * 252
        sigma = float(sigma_raw) * math.sqrt(252)
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
        prices_arr = close.values.astype(float)
        if np.any(prices_arr <= 0) or np.any(np.isnan(prices_arr)):
            return ForecastResult(
                ticker=ticker, forecast_time=now, horizon_days=horizon,
                model_name="mean_reversion_ou", point_estimate=price,
                lower_bound=price * 0.8, upper_bound=price * 1.2,
                explanation="Non-positive or NaN prices — mean reversion skipped",
                confidence_score=10.0,
            )
        log_prices = np.log(prices_arr)
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
            probability_flat=round(max(0.0, float(1 - prob_up - prob_down)), 4),
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
        mom_20 = float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) >= 21 else 0
        mom_50 = float(close.iloc[-1] / close.iloc[-51] - 1) if len(close) >= 51 else 0
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
            probability_up=round(min(0.95, max(0.05, 0.5 + avg_mom * 2)), 4),
            probability_down=round(min(0.95, max(0.05, 0.5 - avg_mom * 2)), 4),
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

    def _garch_forecast(
        self, returns: pd.Series, price: float, horizon: int, ticker: str, now: dt.datetime,
    ) -> ForecastResult | None:
        """GARCH(1,1)-based forecast using conditional volatility."""
        try:
            from backend.engines.garch import GARCHEngine
            garch = GARCHEngine()
            result = garch.fit(returns.values, horizon_days=horizon)

            if not result.garch_converged or result.forecast_annualized_vol is None:
                return None

            mu = float(returns.mean()) * 252
            sigma = result.forecast_annualized_vol
            dt_frac = horizon / 252

            projected = round(price * math.exp(mu * dt_frac), 2)
            std_dev = sigma * math.sqrt(dt_frac) * price
            lower = round(projected - 1.645 * std_dev, 2)
            upper = round(projected + 1.645 * std_dev, 2)

            # GARCH confidence is higher because it uses time-varying vol
            persistence = result.persistence or 0
            confidence = 60.0 if persistence < 0.99 else 35.0

            # Get current vol from conditional volatility series
            current_vol_ann = None
            if result.conditional_volatility is not None and len(result.conditional_volatility) > 0:
                current_vol_ann = float(result.conditional_volatility[-1]) * math.sqrt(252)

            return ForecastResult(
                ticker=ticker, forecast_time=now, horizon_days=horizon,
                model_name="garch_volatility",
                point_estimate=projected,
                lower_bound=lower, upper_bound=upper,
                assumptions={
                    "garch_omega": round(result.omega, 8) if result.omega else None,
                    "garch_alpha": round(result.alpha, 6) if result.alpha else None,
                    "garch_beta": round(result.beta, 6) if result.beta else None,
                    "persistence": round(persistence, 6),
                    "half_life_days": round(result.half_life_days, 1) if result.half_life_days else None,
                    "current_vol_ann": round(current_vol_ann, 4) if current_vol_ann else None,
                    "forecast_vol_ann": round(sigma, 4),
                    "vol_regime": result.current_regime,
                },
                explanation=(
                    f"GARCH(1,1): persistence={persistence:.4f}, "
                    f"forecast vol={sigma:.1%}, regime={result.current_regime}"
                ),
                confidence_score=confidence,
            )
        except Exception:
            return None

    def _arima_forecast(
        self, returns: pd.Series, price: float, horizon: int, ticker: str, now: dt.datetime,
    ) -> ForecastResult | None:
        """ARIMA-GARCH combined forecast for conditional mean + variance."""
        try:
            from backend.engines.arima_forecast import ARIMAForecastEngine
            arima = ARIMAForecastEngine()
            result = arima.forecast(returns.values, horizon=horizon, price=price)

            if not result.price_forecast:
                return None

            # Use final price forecast as point estimate
            point_est = result.price_forecast[-1] if result.price_forecast else price
            lower = result.price_intervals_95[0][0] if result.price_intervals_95 else price * 0.8
            upper = result.price_intervals_95[0][1] if result.price_intervals_95 else price * 1.2

            ljung_p = result.ljung_box_pvalue

            return ForecastResult(
                ticker=ticker, forecast_time=now, horizon_days=horizon,
                model_name="arima_garch",
                point_estimate=round(point_est, 2),
                lower_bound=round(lower, 2),
                upper_bound=round(upper, 2),
                assumptions={
                    "arima_order": list(result.selected_order) if result.selected_order else None,
                    "aic": round(result.aic, 2) if result.aic else None,
                    "ljung_box_p": round(ljung_p, 4) if ljung_p else None,
                    "adf_statistic": round(result.adf_statistic, 4) if result.adf_statistic else None,
                },
                explanation=(
                    f"ARIMA{result.selected_order}: AIC={result.aic:.1f}, "
                    f"Ljung-Box p={ljung_p:.3f}"
                    if result.aic and ljung_p
                    else f"ARIMA{result.selected_order}"
                ),
                confidence_score=55.0 if ljung_p and ljung_p > 0.05 else 35.0,
            )
        except Exception:
            return None

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
