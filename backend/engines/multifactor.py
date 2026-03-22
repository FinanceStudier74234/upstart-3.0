"""
Multi-Factor Regression Engine — Fama-French style factor decomposition
for UPST returns analysis.

Regresses UPST returns against multiple systematic factors (market, size,
value, momentum, quality, rate sensitivity, credit, volatility) and
provides rolling exposures, contribution decomposition, residual
diagnostics, style classification, and risk decomposition.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_ROLLING_WINDOW: int = 60
_CROWDING_THRESHOLD: float = 0.7
_MIN_OBS_FOR_REGRESSION: int = 30
_SIGNIFICANCE_LEVEL: float = 0.05

# Canonical factor ordering used throughout the engine.
FACTOR_NAMES: list[str] = [
    "market",
    "size",
    "value",
    "momentum",
    "quality",
    "interest_rate",
    "credit",
    "volatility",
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class MultiFactorResult:
    """Complete output of the multi-factor regression engine."""

    # ── Full-sample OLS ──────────────────────────────────────────────────
    factor_names: list[str] = field(default_factory=list)
    betas: dict[str, float] = field(default_factory=dict)
    alpha: float | None = None
    alpha_annualized: float | None = None

    # Statistical significance
    t_stats: dict[str, float] = field(default_factory=dict)
    p_values: dict[str, float] = field(default_factory=dict)
    alpha_t_stat: float | None = None
    alpha_p_value: float | None = None
    r_squared: float | None = None
    adj_r_squared: float | None = None
    f_statistic: float | None = None
    f_p_value: float | None = None

    # ── Rolling factor exposures ─────────────────────────────────────────
    rolling_window: int = _DEFAULT_ROLLING_WINDOW
    rolling_betas: dict[str, np.ndarray] = field(default_factory=dict)
    rolling_alpha: np.ndarray | None = None
    rolling_r_squared: np.ndarray | None = None

    # ── Factor contribution decomposition ────────────────────────────────
    factor_contributions: dict[str, float] = field(default_factory=dict)
    alpha_contribution: float | None = None
    residual_contribution: float | None = None
    total_return: float | None = None

    # ── Factor crowding ──────────────────────────────────────────────────
    factor_correlation_matrix: np.ndarray | None = None
    crowded_pairs: list[tuple[str, str, float]] = field(default_factory=list)
    crowding_risk_flag: bool = False

    # ── Residual diagnostics ─────────────────────────────────────────────
    residuals: np.ndarray | None = None
    jarque_bera_stat: float | None = None
    jarque_bera_p: float | None = None
    residuals_normal: bool | None = None
    durbin_watson: float | None = None
    residuals_autocorrelated: bool | None = None
    breusch_pagan_stat: float | None = None
    breusch_pagan_p: float | None = None
    heteroscedastic: bool | None = None

    # ── Style classification ─────────────────────────────────────────────
    style: str = "unclassified"
    dominant_factor: str | None = None
    dominant_factor_beta: float | None = None
    style_scores: dict[str, float] = field(default_factory=dict)

    # ── Risk decomposition ───────────────────────────────────────────────
    total_variance: float | None = None
    systematic_variance: float | None = None
    idiosyncratic_variance: float | None = None
    systematic_risk_pct: float | None = None
    idiosyncratic_risk_pct: float | None = None
    factor_risk_contributions: dict[str, float] = field(default_factory=dict)

    # ── Observation counts ───────────────────────────────────────────────
    n_observations: int = 0
    n_factors: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class MultiFactorEngine:
    """Fama-French style multi-factor OLS regression engine."""

    # --------------------------------------------------------------------- #
    #  Public entry point                                                     #
    # --------------------------------------------------------------------- #

    def analyze(
        self,
        asset_returns: np.ndarray,
        factor_returns: dict[str, np.ndarray],
        rolling_window: int = _DEFAULT_ROLLING_WINDOW,
    ) -> MultiFactorResult:
        """Run the full multi-factor analysis pipeline.

        Parameters
        ----------
        asset_returns:
            1-D array of asset (UPST) daily returns.
        factor_returns:
            Mapping of factor name -> 1-D return series.  Missing or
            all-NaN factors are silently excluded.
        rolling_window:
            Window size (trading days) for rolling regressions.

        Returns
        -------
        MultiFactorResult with all computed fields populated.
        """
        result = MultiFactorResult(rolling_window=rolling_window)

        # ── Sanitise inputs ──────────────────────────────────────────────
        asset_returns = np.asarray(asset_returns, dtype=np.float64).ravel()
        factor_matrix, valid_names = self._build_factor_matrix(
            asset_returns, factor_returns,
        )

        if factor_matrix is None or len(asset_returns) < _MIN_OBS_FOR_REGRESSION:
            return result

        result.factor_names = valid_names
        result.n_factors = len(valid_names)
        result.n_observations = len(asset_returns)

        # ── Core OLS ─────────────────────────────────────────────────────
        self._run_ols(asset_returns, factor_matrix, valid_names, result)

        # ── Rolling regressions ──────────────────────────────────────────
        self._run_rolling(asset_returns, factor_matrix, valid_names, rolling_window, result)

        # ── Factor contribution decomposition ────────────────────────────
        self._decompose_contributions(asset_returns, factor_matrix, valid_names, result)

        # ── Factor crowding detection ────────────────────────────────────
        self._detect_crowding(factor_matrix, valid_names, result)

        # ── Residual diagnostics ─────────────────────────────────────────
        self._residual_diagnostics(asset_returns, factor_matrix, result)

        # ── Style classification ─────────────────────────────────────────
        self._classify_style(result)

        # ── Risk decomposition ───────────────────────────────────────────
        self._decompose_risk(asset_returns, factor_matrix, valid_names, result)

        return result

    # --------------------------------------------------------------------- #
    #  Input preparation                                                      #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _build_factor_matrix(
        asset_returns: np.ndarray,
        factor_returns: dict[str, np.ndarray],
    ) -> tuple[np.ndarray | None, list[str]]:
        """Build an (n, k) factor matrix from the dict, aligning lengths.

        Factors that are None, wrong length, or all-NaN are excluded.
        """
        n = len(asset_returns)
        valid_names: list[str] = []
        columns: list[np.ndarray] = []

        for name in FACTOR_NAMES:
            arr = factor_returns.get(name)
            if arr is None:
                continue
            arr = np.asarray(arr, dtype=np.float64).ravel()
            if len(arr) != n:
                continue
            if np.all(np.isnan(arr)):
                continue
            # Replace any remaining NaNs with 0 (neutral return)
            arr = np.where(np.isnan(arr), 0.0, arr)
            valid_names.append(name)
            columns.append(arr)

        # Also accept non-canonical factor names the caller may supply.
        for name, arr in factor_returns.items():
            if name in valid_names or name in FACTOR_NAMES:
                continue
            arr = np.asarray(arr, dtype=np.float64).ravel()
            if len(arr) != n:
                continue
            if np.all(np.isnan(arr)):
                continue
            arr = np.where(np.isnan(arr), 0.0, arr)
            valid_names.append(name)
            columns.append(arr)

        if not columns:
            return None, []

        return np.column_stack(columns), valid_names

    # --------------------------------------------------------------------- #
    #  Full-sample OLS                                                        #
    # --------------------------------------------------------------------- #

    def _run_ols(
        self,
        y: np.ndarray,
        X_raw: np.ndarray,
        names: list[str],
        result: MultiFactorResult,
    ) -> None:
        """OLS with intercept: y = alpha + X @ beta + epsilon."""
        n, k = X_raw.shape
        X = np.column_stack([np.ones(n), X_raw])  # prepend intercept

        try:
            coeffs, residuals_ss, rank, sv = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError:
            return

        if rank < k + 1:
            # Near-singular — still store coefficients but flag significance.
            pass

        alpha_hat = float(coeffs[0])
        beta_hat = coeffs[1:]

        result.alpha = round(alpha_hat, 8)
        result.alpha_annualized = round(alpha_hat * 252, 6)

        for i, name in enumerate(names):
            result.betas[name] = round(float(beta_hat[i]), 6)

        # Residuals and R-squared
        y_hat = X @ coeffs
        resid = y - y_hat
        result.residuals = resid

        ss_res = float(np.sum(resid ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))

        if ss_tot > 0:
            r2 = 1.0 - ss_res / ss_tot
            result.r_squared = round(max(0.0, r2), 6)
            adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / max(n - k - 1, 1)
            result.adj_r_squared = round(adj_r2, 6)
        else:
            result.r_squared = 0.0
            result.adj_r_squared = 0.0

        # Standard errors, t-stats, p-values
        dof = max(n - k - 1, 1)
        mse = ss_res / dof

        try:
            XtX_inv = np.linalg.inv(X.T @ X)
        except np.linalg.LinAlgError:
            XtX_inv = np.linalg.pinv(X.T @ X)

        se = np.sqrt(np.maximum(np.diag(XtX_inv) * mse, 0.0))

        # Alpha t-stat / p-value
        if se[0] > 0:
            t_alpha = alpha_hat / se[0]
            result.alpha_t_stat = round(float(t_alpha), 4)
            result.alpha_p_value = round(float(2 * stats.t.sf(abs(t_alpha), dof)), 6)
        else:
            result.alpha_t_stat = 0.0
            result.alpha_p_value = 1.0

        # Beta t-stats / p-values
        for i, name in enumerate(names):
            idx = i + 1
            if se[idx] > 0:
                t_val = float(beta_hat[i]) / se[idx]
                p_val = float(2 * stats.t.sf(abs(t_val), dof))
                result.t_stats[name] = round(t_val, 4)
                result.p_values[name] = round(p_val, 6)
            else:
                result.t_stats[name] = 0.0
                result.p_values[name] = 1.0

        # F-statistic for overall model significance
        if k > 0 and ss_tot > 0:
            ms_model = (ss_tot - ss_res) / max(k, 1)
            ms_resid = mse
            if ms_resid > 0:
                f_stat = ms_model / ms_resid
                result.f_statistic = round(float(f_stat), 4)
                result.f_p_value = round(
                    float(stats.f.sf(f_stat, k, dof)), 6,
                )

    # --------------------------------------------------------------------- #
    #  Rolling regressions                                                    #
    # --------------------------------------------------------------------- #

    def _run_rolling(
        self,
        y: np.ndarray,
        X_raw: np.ndarray,
        names: list[str],
        window: int,
        result: MultiFactorResult,
    ) -> None:
        n = len(y)
        if n < window:
            return

        k = X_raw.shape[1]
        n_windows = n - window + 1

        rolling_alpha = np.full(n_windows, np.nan)
        rolling_betas = {name: np.full(n_windows, np.nan) for name in names}
        rolling_r2 = np.full(n_windows, np.nan)

        for t in range(n_windows):
            y_w = y[t: t + window]
            X_w = np.column_stack([np.ones(window), X_raw[t: t + window]])

            try:
                coeffs, _, rank, _ = np.linalg.lstsq(X_w, y_w, rcond=None)
            except np.linalg.LinAlgError:
                continue

            rolling_alpha[t] = coeffs[0]
            for i, name in enumerate(names):
                rolling_betas[name][t] = coeffs[i + 1]

            y_hat = X_w @ coeffs
            ss_res = float(np.sum((y_w - y_hat) ** 2))
            ss_tot = float(np.sum((y_w - np.mean(y_w)) ** 2))
            if ss_tot > 0:
                rolling_r2[t] = max(0.0, 1.0 - ss_res / ss_tot)

        result.rolling_alpha = rolling_alpha
        result.rolling_betas = rolling_betas
        result.rolling_r_squared = rolling_r2

    # --------------------------------------------------------------------- #
    #  Factor contribution decomposition                                      #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _decompose_contributions(
        y: np.ndarray,
        X_raw: np.ndarray,
        names: list[str],
        result: MultiFactorResult,
    ) -> None:
        """Decompose cumulative return: alpha + sum(beta_i * F_i) + residual."""
        if result.alpha is None:
            return

        total_ret = float(np.sum(y))
        result.total_return = round(total_ret, 8)

        alpha_contrib = result.alpha * len(y)
        result.alpha_contribution = round(alpha_contrib, 8)

        residual_sum = 0.0
        for i, name in enumerate(names):
            beta = result.betas.get(name, 0.0)
            factor_sum = float(np.sum(X_raw[:, i]))
            contrib = beta * factor_sum
            result.factor_contributions[name] = round(contrib, 8)
            residual_sum += contrib

        result.residual_contribution = round(
            total_ret - alpha_contrib - residual_sum, 8,
        )

    # --------------------------------------------------------------------- #
    #  Factor crowding detection                                              #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _detect_crowding(
        X_raw: np.ndarray,
        names: list[str],
        result: MultiFactorResult,
    ) -> None:
        k = X_raw.shape[1]
        if k < 2:
            return

        corr = np.corrcoef(X_raw, rowvar=False)
        result.factor_correlation_matrix = np.round(corr, 6)

        crowded: list[tuple[str, str, float]] = []
        for i in range(k):
            for j in range(i + 1, k):
                c = float(corr[i, j])
                if abs(c) > _CROWDING_THRESHOLD:
                    crowded.append((names[i], names[j], round(c, 4)))

        result.crowded_pairs = crowded
        result.crowding_risk_flag = len(crowded) > 0

    # --------------------------------------------------------------------- #
    #  Residual diagnostics                                                   #
    # --------------------------------------------------------------------- #

    def _residual_diagnostics(
        self,
        y: np.ndarray,
        X_raw: np.ndarray,
        result: MultiFactorResult,
    ) -> None:
        resid = result.residuals
        if resid is None or len(resid) < _MIN_OBS_FOR_REGRESSION:
            return

        # Jarque-Bera normality test
        jb_stat, jb_p = stats.jarque_bera(resid)
        result.jarque_bera_stat = round(float(jb_stat), 4)
        result.jarque_bera_p = round(float(jb_p), 6)
        result.residuals_normal = float(jb_p) > _SIGNIFICANCE_LEVEL

        # Durbin-Watson autocorrelation test
        dw = self._durbin_watson(resid)
        result.durbin_watson = round(dw, 4)
        # DW ~ 2 means no autocorrelation; <1.5 or >2.5 is concerning
        result.residuals_autocorrelated = dw < 1.5 or dw > 2.5

        # Breusch-Pagan heteroscedasticity test (auxiliary regression)
        bp_stat, bp_p = self._breusch_pagan(resid, X_raw)
        result.breusch_pagan_stat = round(bp_stat, 4)
        result.breusch_pagan_p = round(bp_p, 6)
        result.heteroscedastic = bp_p < _SIGNIFICANCE_LEVEL

    @staticmethod
    def _durbin_watson(residuals: np.ndarray) -> float:
        diff = np.diff(residuals)
        dw = float(np.sum(diff ** 2) / max(np.sum(residuals ** 2), 1e-15))
        return dw

    @staticmethod
    def _breusch_pagan(residuals: np.ndarray, X_raw: np.ndarray) -> tuple[float, float]:
        """Breusch-Pagan test for heteroscedasticity.

        Regresses squared residuals on the original regressors and tests
        whether the explained sum of squares is significant under chi-squared.
        """
        n, k = X_raw.shape
        u2 = residuals ** 2
        u2_norm = u2 / max(float(np.mean(u2)), 1e-15)

        X_bp = np.column_stack([np.ones(n), X_raw])
        try:
            coeffs, _, _, _ = np.linalg.lstsq(X_bp, u2_norm, rcond=None)
        except np.linalg.LinAlgError:
            return 0.0, 1.0

        fitted = X_bp @ coeffs
        ss_model = float(np.sum((fitted - np.mean(u2_norm)) ** 2))
        bp_stat = ss_model / 2.0
        bp_p = float(stats.chi2.sf(bp_stat, k))
        return bp_stat, bp_p

    # --------------------------------------------------------------------- #
    #  Style classification                                                   #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _classify_style(result: MultiFactorResult) -> None:
        """Classify UPST's style based on dominant factor loadings.

        Categories: growth, value, momentum, quality, rate_sensitive,
        credit_sensitive, volatility_driven, market_beta, blend.
        """
        if not result.betas:
            return

        # Map factor names to style labels.
        style_map: dict[str, str] = {
            "market": "market_beta",
            "size": "small_cap_tilt" if result.betas.get("size", 0) > 0 else "large_cap_tilt",
            "value": "value",
            "momentum": "momentum",
            "quality": "quality",
            "interest_rate": "rate_sensitive",
            "credit": "credit_sensitive",
            "volatility": "volatility_driven",
        }

        # Compute style scores as |beta * significance|.  We weight by
        # significance so that a large but statistically meaningless beta
        # does not dominate the classification.
        scores: dict[str, float] = {}
        for name, beta in result.betas.items():
            p = result.p_values.get(name, 1.0)
            significance_weight = max(0.0, 1.0 - p)
            scores[name] = abs(beta) * significance_weight

        result.style_scores = {k: round(v, 6) for k, v in scores.items()}

        if not scores:
            return

        dominant = max(scores, key=scores.get)  # type: ignore[arg-type]
        result.dominant_factor = dominant
        result.dominant_factor_beta = result.betas.get(dominant)

        # Primary style classification — negative value beta => growth.
        value_beta = result.betas.get("value", 0.0)
        mom_beta = result.betas.get("momentum", 0.0)
        quality_beta = result.betas.get("quality", 0.0)
        rate_beta = result.betas.get("interest_rate", 0.0)

        if dominant == "value" and value_beta > 0:
            result.style = "value"
        elif dominant == "value" and value_beta < 0:
            result.style = "growth"
        elif dominant == "momentum":
            result.style = "momentum"
        elif dominant == "quality":
            result.style = "quality"
        elif dominant == "interest_rate":
            result.style = "rate_sensitive"
        elif dominant == "credit":
            result.style = "credit_sensitive"
        elif dominant == "volatility":
            result.style = "volatility_driven"
        elif dominant == "market":
            result.style = "market_beta"
        else:
            # Fall back to value vs growth heuristic.
            if value_beta < -0.3:
                result.style = "growth"
            elif value_beta > 0.3:
                result.style = "value"
            else:
                result.style = "blend"

    # --------------------------------------------------------------------- #
    #  Risk decomposition                                                     #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _decompose_risk(
        y: np.ndarray,
        X_raw: np.ndarray,
        names: list[str],
        result: MultiFactorResult,
    ) -> None:
        """Decompose total return variance into systematic and idiosyncratic.

        Systematic variance = Var(X @ beta).
        Idiosyncratic variance = Var(residual).
        Factor-level contributions use the marginal variance approach:
          Var_i = beta_i^2 * Var(F_i) + sum_{j!=i} beta_i * beta_j * Cov(F_i, F_j)
        """
        if result.residuals is None:
            return

        total_var = float(np.var(y, ddof=1))
        if total_var <= 0:
            return

        result.total_variance = round(total_var, 10)

        resid_var = float(np.var(result.residuals, ddof=1))
        systematic_var = max(0.0, total_var - resid_var)

        result.systematic_variance = round(systematic_var, 10)
        result.idiosyncratic_variance = round(resid_var, 10)
        result.systematic_risk_pct = round(systematic_var / total_var * 100, 2)
        result.idiosyncratic_risk_pct = round(resid_var / total_var * 100, 2)

        # Per-factor risk contribution via covariance decomposition.
        k = X_raw.shape[1]
        cov_factors = np.cov(X_raw, rowvar=False)
        if cov_factors.ndim == 0:
            cov_factors = np.array([[float(cov_factors)]])

        beta_vec = np.array([result.betas.get(n, 0.0) for n in names])

        for i, name in enumerate(names):
            # Marginal contribution: beta_i * sum_j(beta_j * Cov(F_i, F_j))
            marginal = float(beta_vec[i] * np.dot(cov_factors[i, :], beta_vec))
            pct = marginal / total_var * 100 if total_var > 0 else 0.0
            result.factor_risk_contributions[name] = round(pct, 4)
