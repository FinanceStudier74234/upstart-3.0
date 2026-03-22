"""
Copula-Based Tail Dependence Engine
Gaussian and Student-t copula fitting, tail dependence coefficients,
conditional VaR, joint drawdown probabilities, and diversification benefit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np
from scipy import optimize, stats, special


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MIN_OBS = 50
_TAIL_QUANTILE = 0.05  # 5th percentile for tail analysis
_DEFAULT_DF = 5.0       # default degrees of freedom for Student-t copula
_DF_BOUNDS = (2.01, 50.0)
_CORR_BOUNDS = (-0.999, 0.999)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class CopulaRiskResult:
    """Full output of the copula risk engine."""
    # Gaussian copula
    gaussian_rho: float | None = None
    gaussian_joint_tail_prob: float | None = None

    # Student-t copula
    student_t_rho: float | None = None
    student_t_df: float | None = None
    student_t_joint_tail_prob: float | None = None

    # Tail dependence coefficients
    lambda_upper: float | None = None
    lambda_lower: float | None = None

    # Conditional VaR
    conditional_var_5pct: float | None = None  # VaR of UPST | SPY at 5th pctile
    unconditional_var_5pct: float | None = None

    # Joint drawdown probabilities
    joint_drawdown_prob_5_5: float | None = None    # P(UPST < -5% AND SPY < -5%)
    joint_drawdown_prob_10_5: float | None = None   # P(UPST < -10% AND SPY < -5%)
    joint_drawdown_prob_10_10: float | None = None  # P(UPST < -10% AND SPY < -10%)

    # Diversification benefit
    portfolio_var_with_copula: float | None = None
    portfolio_var_naive: float | None = None
    diversification_gap_pct: float | None = None  # how much naive underestimates


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class CopulaRiskEngine:
    """
    Copula-based tail dependence and joint risk analysis.

    Fits Gaussian and Student-t copulas to model the dependence structure
    between UPST and SPY returns, with emphasis on tail risk.
    """

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def analyze(
        self,
        upst_returns: np.ndarray,
        spy_returns: np.ndarray,
    ) -> CopulaRiskResult:
        """Fit copulas and compute all tail risk metrics."""
        result = CopulaRiskResult()

        upst_returns = np.asarray(upst_returns, dtype=np.float64).ravel()
        spy_returns = np.asarray(spy_returns, dtype=np.float64).ravel()

        n = min(len(upst_returns), len(spy_returns))
        if n < _MIN_OBS:
            return result

        u = upst_returns[:n].copy()
        s = spy_returns[:n].copy()

        # Clean
        mask = np.isfinite(u) & np.isfinite(s)
        u = u[mask]
        s = s[mask]
        if len(u) < _MIN_OBS:
            return result

        # --- Rank-transform to pseudo-observations (uniform margins) ---
        u_rank = self._pseudo_obs(u)
        s_rank = self._pseudo_obs(s)

        # --- Gaussian copula ---
        g_rho = self._fit_gaussian_copula(u_rank, s_rank)
        result.gaussian_rho = g_rho
        result.gaussian_joint_tail_prob = self._gaussian_joint_tail(
            g_rho, _TAIL_QUANTILE,
        )

        # --- Student-t copula ---
        t_rho, t_df = self._fit_student_t_copula(u_rank, s_rank)
        result.student_t_rho = t_rho
        result.student_t_df = t_df
        result.student_t_joint_tail_prob = self._student_t_joint_tail(
            t_rho, t_df, _TAIL_QUANTILE,
        )

        # --- Tail dependence coefficients ---
        lam_u, lam_l = self._tail_dependence(t_rho, t_df)
        result.lambda_upper = lam_u
        result.lambda_lower = lam_l

        # --- Conditional VaR ---
        cond_var, uncond_var = self._conditional_var(u, s, u_rank, s_rank, t_rho, t_df)
        result.conditional_var_5pct = cond_var
        result.unconditional_var_5pct = uncond_var

        # --- Joint drawdown probabilities ---
        dd_probs = self._joint_drawdown_probs(u, s, t_rho, t_df)
        result.joint_drawdown_prob_5_5 = dd_probs.get((0.05, 0.05))
        result.joint_drawdown_prob_10_5 = dd_probs.get((0.10, 0.05))
        result.joint_drawdown_prob_10_10 = dd_probs.get((0.10, 0.10))

        # --- Diversification benefit ---
        copula_var, naive_var, gap = self._diversification_benefit(
            u, s, t_rho, t_df,
        )
        result.portfolio_var_with_copula = copula_var
        result.portfolio_var_naive = naive_var
        result.diversification_gap_pct = gap

        return result

    # ------------------------------------------------------------------ #
    # Pseudo-observations (rank transform)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _pseudo_obs(x: np.ndarray) -> np.ndarray:
        """
        Transform to pseudo-observations on (0, 1).
        Uses ranks / (n+1) to avoid 0 and 1.
        """
        n = len(x)
        ranks = stats.rankdata(x, method="ordinal")
        return ranks / (n + 1)

    # ------------------------------------------------------------------ #
    # Gaussian copula
    # ------------------------------------------------------------------ #
    def _fit_gaussian_copula(
        self,
        u: np.ndarray,
        v: np.ndarray,
    ) -> float:
        """
        Fit Gaussian copula by maximum likelihood.
        The only parameter is the correlation rho.
        """
        # Transform to standard normal
        z_u = stats.norm.ppf(u)
        z_v = stats.norm.ppf(v)

        def neg_log_lik(rho_arr: np.ndarray) -> float:
            rho = float(rho_arr[0])
            rho = np.clip(rho, -0.999, 0.999)
            det = 1.0 - rho * rho
            if det < 1e-12:
                return 1e12
            n = len(z_u)
            # Gaussian copula density log c = -0.5 * [log(det) + (rho^2*(u^2+v^2) - 2*rho*u*v) / det]
            nll = 0.5 * n * math.log(det)
            quad = rho * rho * (z_u ** 2 + z_v ** 2) - 2.0 * rho * z_u * z_v
            nll += 0.5 * np.sum(quad / det)
            return nll  # already negative log-lik (positive)

        # Use sample correlation as starting point
        rho_init = float(np.corrcoef(z_u, z_v)[0, 1])
        if not np.isfinite(rho_init):
            rho_init = 0.0

        try:
            res = optimize.minimize_scalar(
                lambda r: neg_log_lik(np.array([r])),
                bounds=(-0.999, 0.999),
                method="bounded",
            )
            rho = float(np.clip(res.x, -0.999, 0.999))
        except Exception:
            rho = rho_init

        return rho

    @staticmethod
    def _gaussian_joint_tail(rho: float, q: float) -> float:
        """P(U < q, V < q) under Gaussian copula."""
        z_q = stats.norm.ppf(q)
        # Bivariate normal CDF
        from scipy.stats import mvn
        low = np.array([-10.0, -10.0])
        high = np.array([z_q, z_q])
        corr = np.array([[1.0, rho], [rho, 1.0]])
        # Use scipy's mvn
        try:
            prob, _ = mvn.mvnun(low, high, np.array([0.0, 0.0]), corr)
            return float(max(prob, 0.0))
        except Exception:
            # Fallback: independence
            return q * q

    # ------------------------------------------------------------------ #
    # Student-t copula
    # ------------------------------------------------------------------ #
    def _fit_student_t_copula(
        self,
        u: np.ndarray,
        v: np.ndarray,
    ) -> Tuple[float, float]:
        """
        Fit Student-t copula (rho, nu) by maximum likelihood.
        """
        # Starting values
        z_u = stats.norm.ppf(u)
        z_v = stats.norm.ppf(v)
        rho_init = float(np.clip(np.corrcoef(z_u, z_v)[0, 1], -0.99, 0.99))
        if not np.isfinite(rho_init):
            rho_init = 0.0

        def neg_log_lik(params: np.ndarray) -> float:
            rho = float(np.clip(params[0], *_CORR_BOUNDS))
            nu = float(np.clip(params[1], *_DF_BOUNDS))
            det = 1.0 - rho * rho
            if det < 1e-12:
                return 1e12

            # Transform pseudo-obs to t-quantiles
            t_u = stats.t.ppf(u, df=nu)
            t_v = stats.t.ppf(v, df=nu)

            n = len(u)
            half_nu = nu / 2.0
            half_nu1 = (nu + 1.0) / 2.0
            half_nu2 = (nu + 2.0) / 2.0

            # Log copula density for bivariate Student-t
            # c(u,v) = f_{2,R,nu}(t^{-1}(u), t^{-1}(v)) / (f_{1,nu}(t^{-1}(u)) * f_{1,nu}(t^{-1}(v)))
            nll = 0.0

            # Log of joint density constant terms
            log_const = (
                special.gammaln(half_nu2)
                + special.gammaln(half_nu)
                - 2.0 * special.gammaln(half_nu1)
                - 0.5 * math.log(det)
            )

            quad = (t_u ** 2 + t_v ** 2 - 2.0 * rho * t_u * t_v) / det
            log_joint = -half_nu2 * np.log(1.0 + quad / nu)

            # Marginal t densities (log)
            log_marg_u = -half_nu1 * np.log(1.0 + t_u ** 2 / nu)
            log_marg_v = -half_nu1 * np.log(1.0 + t_v ** 2 / nu)

            log_copula = log_const + log_joint - log_marg_u - log_marg_v
            nll = -np.sum(log_copula)

            if not np.isfinite(nll):
                return 1e12
            return nll

        try:
            res = optimize.minimize(
                neg_log_lik,
                x0=np.array([rho_init, _DEFAULT_DF]),
                method="Nelder-Mead",
                options={"maxiter": 1000, "xatol": 1e-5, "fatol": 1e-5},
            )
            if res.success or np.isfinite(res.fun):
                rho = float(np.clip(res.x[0], *_CORR_BOUNDS))
                nu = float(np.clip(res.x[1], *_DF_BOUNDS))
            else:
                rho, nu = rho_init, _DEFAULT_DF
        except Exception:
            rho, nu = rho_init, _DEFAULT_DF

        return rho, nu

    def _student_t_joint_tail(
        self,
        rho: float,
        nu: float,
        q: float,
        n_sim: int = 50_000,
    ) -> float:
        """P(U < q, V < q) under Student-t copula (via simulation)."""
        rng = np.random.RandomState(42)
        samples = self._sample_t_copula(rho, nu, n_sim, rng)
        prob = float(np.mean((samples[:, 0] < q) & (samples[:, 1] < q)))
        return prob

    @staticmethod
    def _sample_t_copula(
        rho: float,
        nu: float,
        n: int,
        rng: np.random.RandomState,
    ) -> np.ndarray:
        """
        Sample from bivariate Student-t copula.

        Method: generate bivariate t via scale mixture of normals,
        then transform margins to uniform.
        """
        # Covariance matrix
        cov = np.array([[1.0, rho], [rho, 1.0]])
        L = np.linalg.cholesky(cov)

        # Standard normal draws
        z = rng.standard_normal((n, 2))
        z = z @ L.T

        # Chi-squared for scale mixture
        chi2 = rng.chisquare(df=nu, size=n)
        scale = np.sqrt(nu / chi2)

        # Bivariate t samples
        t_samples = z * scale[:, np.newaxis]

        # Transform to uniform via t-CDF
        u = stats.t.cdf(t_samples, df=nu)
        return u

    # ------------------------------------------------------------------ #
    # Tail dependence coefficients
    # ------------------------------------------------------------------ #
    @staticmethod
    def _tail_dependence(rho: float, nu: float) -> Tuple[float, float]:
        """
        Analytic tail dependence for Student-t copula.

        lambda = 2 * t_{nu+1}(-sqrt((nu+1)(1-rho)/(1+rho)))

        For the Student-t copula, upper and lower tail dependence are equal
        (symmetric copula).
        """
        if nu <= 0 or not np.isfinite(nu):
            return 0.0, 0.0

        ratio = (1.0 - rho) / (1.0 + rho)
        if ratio < 0:
            ratio = 0.0
        arg = -math.sqrt((nu + 1.0) * ratio)
        lam = 2.0 * stats.t.cdf(arg, df=nu + 1.0)
        lam = float(np.clip(lam, 0.0, 1.0))
        return lam, lam  # symmetric: lambda_U = lambda_L

    # ------------------------------------------------------------------ #
    # Conditional VaR
    # ------------------------------------------------------------------ #
    def _conditional_var(
        self,
        upst: np.ndarray,
        spy: np.ndarray,
        u_rank: np.ndarray,
        s_rank: np.ndarray,
        rho: float,
        nu: float,
        n_sim: int = 50_000,
    ) -> Tuple[float, float]:
        """
        VaR of UPST conditional on SPY being in its lower tail.

        Returns (conditional_var_5pct, unconditional_var_5pct).
        """
        # Unconditional VaR (5th percentile of UPST returns)
        uncond_var = float(np.percentile(upst, 5))

        # Simulate from t-copula
        rng = np.random.RandomState(123)
        samples = self._sample_t_copula(rho, nu, n_sim, rng)

        # Condition on SPY being below 5th percentile
        spy_tail_mask = samples[:, 1] < _TAIL_QUANTILE
        if np.sum(spy_tail_mask) < 10:
            return uncond_var, uncond_var

        # Map UPST copula draws back to return space via empirical quantile
        upst_sorted = np.sort(upst)
        n_data = len(upst_sorted)
        upst_cond_u = samples[spy_tail_mask, 0]

        # Map uniform draws to empirical returns
        indices = np.clip(
            (upst_cond_u * n_data).astype(int), 0, n_data - 1,
        )
        upst_cond_returns = upst_sorted[indices]

        cond_var = float(np.percentile(upst_cond_returns, 5))

        return cond_var, uncond_var

    # ------------------------------------------------------------------ #
    # Joint drawdown probabilities
    # ------------------------------------------------------------------ #
    def _joint_drawdown_probs(
        self,
        upst: np.ndarray,
        spy: np.ndarray,
        rho: float,
        nu: float,
        n_sim: int = 100_000,
    ) -> dict:
        """
        P(UPST < -X% AND SPY < -Y%) for various thresholds,
        computed via copula simulation.
        """
        rng = np.random.RandomState(456)
        samples = self._sample_t_copula(rho, nu, n_sim, rng)

        # Map uniform to empirical returns
        upst_sorted = np.sort(upst)
        spy_sorted = np.sort(spy)
        n_u, n_s = len(upst_sorted), len(spy_sorted)

        idx_u = np.clip((samples[:, 0] * n_u).astype(int), 0, n_u - 1)
        idx_s = np.clip((samples[:, 1] * n_s).astype(int), 0, n_s - 1)

        sim_upst = upst_sorted[idx_u]
        sim_spy = spy_sorted[idx_s]

        result = {}
        for upst_thresh, spy_thresh in [(0.05, 0.05), (0.10, 0.05), (0.10, 0.10)]:
            prob = float(np.mean(
                (sim_upst < -upst_thresh) & (sim_spy < -spy_thresh)
            ))
            result[(upst_thresh, spy_thresh)] = prob

        return result

    # ------------------------------------------------------------------ #
    # Diversification benefit
    # ------------------------------------------------------------------ #
    def _diversification_benefit(
        self,
        upst: np.ndarray,
        spy: np.ndarray,
        rho: float,
        nu: float,
        weight_upst: float = 0.5,
        n_sim: int = 100_000,
    ) -> Tuple[float, float, float]:
        """
        Compare portfolio VaR using copula vs. naive Gaussian correlation.

        Returns (copula_var, naive_var, gap_pct).
        """
        rng = np.random.RandomState(789)

        # --- Copula-based portfolio VaR ---
        samples = self._sample_t_copula(rho, nu, n_sim, rng)
        upst_sorted = np.sort(upst)
        spy_sorted = np.sort(spy)
        n_u, n_s = len(upst_sorted), len(spy_sorted)

        idx_u = np.clip((samples[:, 0] * n_u).astype(int), 0, n_u - 1)
        idx_s = np.clip((samples[:, 1] * n_s).astype(int), 0, n_s - 1)

        port_copula = weight_upst * upst_sorted[idx_u] + (1 - weight_upst) * spy_sorted[idx_s]
        copula_var = float(np.percentile(port_copula, 5))

        # --- Naive Gaussian portfolio VaR ---
        mu_u, sig_u = float(np.mean(upst)), float(np.std(upst, ddof=1))
        mu_s, sig_s = float(np.mean(spy)), float(np.std(spy, ddof=1))
        pearson_rho = float(np.corrcoef(upst, spy)[0, 1])
        if not np.isfinite(pearson_rho):
            pearson_rho = 0.0

        port_mu = weight_upst * mu_u + (1 - weight_upst) * mu_s
        port_var = (
            (weight_upst * sig_u) ** 2
            + ((1 - weight_upst) * sig_s) ** 2
            + 2 * weight_upst * (1 - weight_upst) * pearson_rho * sig_u * sig_s
        )
        port_sig = math.sqrt(max(port_var, 1e-15))
        naive_var = float(port_mu + stats.norm.ppf(0.05) * port_sig)

        # Gap: how much does naive underestimate tail risk?
        if abs(naive_var) > 1e-10:
            gap = (copula_var - naive_var) / abs(naive_var) * 100.0
        else:
            gap = 0.0

        return copula_var, naive_var, float(gap)
