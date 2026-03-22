"""
Hidden Markov Model Regime Detection Engine
Gaussian HMM with 3 states (Bull / Neutral / Bear) fit via Baum-Welch EM.
All HMM math implemented from scratch — no hmmlearn dependency.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List

import numpy as np
from scipy import stats as sp_stats


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class Regime(IntEnum):
    BULL = 0
    NEUTRAL = 1
    BEAR = 2


_REGIME_LABELS: dict[int, str] = {
    Regime.BULL: "Bull",
    Regime.NEUTRAL: "Neutral",
    Regime.BEAR: "Bear",
}

_NUM_STATES = 3
_DEFAULT_MAX_ITER = 100
_DEFAULT_TOL = 1e-6
_MIN_VARIANCE = 1e-8  # floor to prevent degenerate emissions
_FORECAST_HORIZONS = (1, 5, 21)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RegimeConditionalStats:
    """Per-regime distributional statistics."""
    regime: str = ""
    mean_return: float | None = None
    volatility: float | None = None
    annualized_return: float | None = None
    annualized_volatility: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    num_observations: int = 0
    fraction_of_time: float = 0.0


@dataclass
class RegimeChangeAlert:
    """Alert raised when regime probability shifts abruptly."""
    day_index: int = 0
    from_regime: str = ""
    to_regime: str = ""
    probability_shift: float = 0.0
    current_probability: float = 0.0


@dataclass
class HMMRegimeResult:
    """Complete output of the HMM regime detection engine."""

    # --- Regime labels & decoded sequence ---
    regime_labels: list[str] = field(default_factory=list)
    viterbi_sequence: np.ndarray | None = None          # (T,) most-likely state ids
    viterbi_labels: list[str] = field(default_factory=list)

    # --- Current regime probabilities (filtered) ---
    current_regime: str = ""
    current_regime_probabilities: dict[str, float] = field(default_factory=dict)

    # --- Full smoothed posteriors (T x K) ---
    smoothed_probabilities: np.ndarray | None = None

    # --- Transition matrix & expected durations ---
    transition_matrix: np.ndarray | None = None          # (K, K)
    expected_regime_duration: dict[str, float] = field(default_factory=dict)

    # --- Emission parameters ---
    emission_means: np.ndarray | None = None             # (K,)
    emission_variances: np.ndarray | None = None         # (K,)
    initial_distribution: np.ndarray | None = None       # (K,)

    # --- Regime forecasts at t+1, t+5, t+21 ---
    regime_forecast: dict[int, dict[str, float]] = field(default_factory=dict)

    # --- Regime-conditional statistics ---
    regime_statistics: list[RegimeConditionalStats] = field(default_factory=list)

    # --- Regime change alerts ---
    regime_change_alerts: list[RegimeChangeAlert] = field(default_factory=list)

    # --- Convergence info ---
    converged: bool = False
    iterations: int = 0
    final_log_likelihood: float = 0.0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class HMMRegimeEngine:
    """
    Gaussian Hidden Markov Model with 3 regimes.

    Implements the full Baum-Welch (EM) training loop, Viterbi decoding,
    forward filtering, and regime forecasting using only numpy / scipy.

    Parameters
    ----------
    n_states : int
        Number of hidden states (default 3).
    max_iterations : int
        Maximum EM iterations (default 100).
    tolerance : float
        Log-likelihood convergence tolerance (default 1e-6).
    random_seed : int | None
        Seed for reproducible k-means initialisation.
    """

    def __init__(
        self,
        n_states: int = _NUM_STATES,
        max_iterations: int = _DEFAULT_MAX_ITER,
        tolerance: float = _DEFAULT_TOL,
        random_seed: int | None = 42,
    ) -> None:
        self.n_states = n_states
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.random_seed = random_seed

        # model parameters (set during fit)
        self._pi: np.ndarray | None = None       # (K,)   initial state distribution
        self._A: np.ndarray | None = None         # (K,K)  transition matrix
        self._means: np.ndarray | None = None     # (K,)   emission means
        self._vars: np.ndarray | None = None      # (K,)   emission variances

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, returns: np.ndarray) -> HMMRegimeResult:
        """
        Fit the Gaussian HMM to a 1-D array of returns and produce all
        regime-detection outputs.

        Parameters
        ----------
        returns : np.ndarray
            1-D array of daily (log or simple) returns.  Length T >= 10.

        Returns
        -------
        HMMRegimeResult
        """
        returns = np.asarray(returns, dtype=np.float64).ravel()
        T = len(returns)
        if T < 10:
            warnings.warn("HMMRegimeEngine requires at least 10 observations; returning empty result.")
            return HMMRegimeResult()

        # --- Initialise parameters via k-means --------------------------
        self._initialise_parameters(returns)

        # --- EM (Baum-Welch) --------------------------------------------
        converged = False
        prev_ll = -np.inf
        iteration = 0

        for iteration in range(1, self.max_iterations + 1):
            # E-step
            log_B = self._log_emission_matrix(returns)             # (T, K)
            log_alpha, ll = self._forward(log_B)                   # (T, K), scalar
            log_beta = self._backward(log_B)                       # (T, K)

            # Check convergence
            if np.isfinite(prev_ll) and abs(ll - prev_ll) < self.tolerance:
                converged = True
                break
            if not np.isfinite(ll):
                warnings.warn(f"EM iteration {iteration}: log-likelihood is non-finite. Stopping early.")
                ll = prev_ll if np.isfinite(prev_ll) else 0.0
                break
            prev_ll = ll

            # Posterior responsibilities  gamma(t,k) = p(z_t=k | O)
            log_gamma = log_alpha + log_beta                       # (T, K)
            log_gamma -= _logsumexp_rows(log_gamma)                # normalise

            # Xi:  xi(t, i, j) = p(z_t=i, z_{t+1}=j | O)
            log_xi = self._compute_log_xi(log_alpha, log_beta, log_B)  # (T-1, K, K)

            # M-step
            self._maximisation(returns, log_gamma, log_xi)

        # --- Final forward / backward with fitted model -----------------
        log_B = self._log_emission_matrix(returns)
        log_alpha, final_ll = self._forward(log_B)
        log_beta = self._backward(log_B)

        log_gamma = log_alpha + log_beta
        log_gamma -= _logsumexp_rows(log_gamma)
        gamma = np.exp(log_gamma)

        # --- Label ordering (Bull/Neutral/Bear by mean descending) ------
        order = np.argsort(-self._means)  # highest mean first
        label_map = {order[i]: i for i in range(self.n_states)}
        gamma = gamma[:, order]
        self._means = self._means[order]
        self._vars = self._vars[order]
        self._A = self._A[np.ix_(order, order)]
        self._pi = self._pi[order]

        # --- Viterbi decoding -------------------------------------------
        viterbi_raw = self._viterbi(returns)
        # remap through label_map
        viterbi_mapped = np.array([label_map[s] for s in viterbi_raw], dtype=np.int32)
        viterbi_labels = [_REGIME_LABELS[s] for s in viterbi_mapped]

        # --- Current regime probabilities (last row of gamma) -----------
        current_probs = gamma[-1]
        current_regime_id = int(np.argmax(current_probs))
        current_regime = _REGIME_LABELS[current_regime_id]

        current_regime_probabilities = {
            _REGIME_LABELS[i]: float(current_probs[i])
            for i in range(self.n_states)
        }

        # --- Expected regime duration -----------------------------------
        expected_duration = {}
        for i in range(self.n_states):
            p_ii = self._A[i, i]
            expected_duration[_REGIME_LABELS[i]] = float(1.0 / max(1.0 - p_ii, 1e-12))

        # --- Regime forecast at t+h (transition matrix powers) ----------
        regime_forecast: dict[int, dict[str, float]] = {}
        for h in _FORECAST_HORIZONS:
            A_h = np.linalg.matrix_power(self._A, h)
            forecast_probs = current_probs @ A_h
            # normalise for numerical safety
            forecast_probs = np.maximum(forecast_probs, 0.0)
            forecast_probs /= forecast_probs.sum() + 1e-15
            regime_forecast[h] = {
                _REGIME_LABELS[i]: float(forecast_probs[i])
                for i in range(self.n_states)
            }

        # --- Regime-conditional statistics ------------------------------
        regime_stats = self._compute_regime_statistics(returns, viterbi_mapped)

        # --- Regime change alerts (>30 % shift in 5 days) ---------------
        regime_change_alerts = self._detect_regime_changes(gamma)

        # --- Assemble result --------------------------------------------
        return HMMRegimeResult(
            regime_labels=list(_REGIME_LABELS.values()),
            viterbi_sequence=viterbi_mapped,
            viterbi_labels=viterbi_labels,
            current_regime=current_regime,
            current_regime_probabilities=current_regime_probabilities,
            smoothed_probabilities=gamma,
            transition_matrix=self._A.copy(),
            expected_regime_duration=expected_duration,
            emission_means=self._means.copy(),
            emission_variances=self._vars.copy(),
            initial_distribution=self._pi.copy(),
            regime_forecast=regime_forecast,
            regime_statistics=regime_stats,
            regime_change_alerts=regime_change_alerts,
            converged=converged,
            iterations=iteration,
            final_log_likelihood=float(final_ll),
        )

    # ------------------------------------------------------------------
    # Initialisation (k-means on returns)
    # ------------------------------------------------------------------

    def _initialise_parameters(self, returns: np.ndarray) -> None:
        """Seed emission parameters using simple k-means on returns."""
        rng = np.random.RandomState(self.random_seed)
        K = self.n_states
        T = len(returns)

        # --- Simple k-means (Lloyd's algorithm) -------------------------
        # Pick K initial centroids by quantile to ensure spread
        quantiles = np.linspace(0, 1, K + 2)[1:-1]
        centroids = np.quantile(returns, quantiles)

        labels = np.zeros(T, dtype=np.int32)
        for _ in range(30):  # max k-means iterations
            # assign
            dists = np.abs(returns[:, None] - centroids[None, :])  # (T, K)
            new_labels = np.argmin(dists, axis=1)
            if np.array_equal(new_labels, labels):
                break
            labels = new_labels
            # update centroids
            for k in range(K):
                mask = labels == k
                if mask.sum() > 0:
                    centroids[k] = returns[mask].mean()

        # Compute cluster means and variances
        means = np.zeros(K)
        variances = np.zeros(K)
        counts = np.zeros(K)
        for k in range(K):
            mask = labels == k
            counts[k] = mask.sum()
            if counts[k] > 1:
                means[k] = returns[mask].mean()
                variances[k] = returns[mask].var() + _MIN_VARIANCE
            elif counts[k] == 1:
                means[k] = returns[mask].mean()
                variances[k] = returns.var() + _MIN_VARIANCE
            else:
                means[k] = rng.normal(0, returns.std())
                variances[k] = returns.var() + _MIN_VARIANCE

        # Uniform initial distribution
        self._pi = np.full(K, 1.0 / K)

        # Transition matrix: mildly persistent (0.9 on diagonal)
        self._A = np.full((K, K), 0.1 / (K - 1))
        np.fill_diagonal(self._A, 0.9)

        self._means = means
        self._vars = variances

    # ------------------------------------------------------------------
    # Emission (log) probability matrix
    # ------------------------------------------------------------------

    def _log_emission_matrix(self, returns: np.ndarray) -> np.ndarray:
        """
        Compute log N(o_t ; mu_k, sigma_k^2) for all t, k.

        Returns shape (T, K).
        """
        T = len(returns)
        K = self.n_states
        log_B = np.empty((T, K))
        for k in range(K):
            var_k = max(self._vars[k], _MIN_VARIANCE)
            diff = returns - self._means[k]
            log_B[:, k] = -0.5 * np.log(2.0 * np.pi * var_k) - 0.5 * diff ** 2 / var_k
        return log_B

    # ------------------------------------------------------------------
    # Forward algorithm (log-space)
    # ------------------------------------------------------------------

    def _forward(self, log_B: np.ndarray) -> tuple[np.ndarray, float]:
        """
        Forward pass in log-space.

        Parameters
        ----------
        log_B : (T, K) log-emission matrix.

        Returns
        -------
        log_alpha : (T, K) forward log-probabilities.
        log_likelihood : scalar total log-likelihood.
        """
        T, K = log_B.shape
        log_alpha = np.full((T, K), -np.inf)
        log_A = np.log(self._A + 1e-300)
        log_pi = np.log(self._pi + 1e-300)

        # t = 0
        log_alpha[0] = log_pi + log_B[0]

        for t in range(1, T):
            for j in range(K):
                # log_alpha[t, j] = log( sum_i alpha[t-1,i] * A[i,j] ) + log_B[t,j]
                log_alpha[t, j] = _logsumexp(log_alpha[t - 1] + log_A[:, j]) + log_B[t, j]

        log_likelihood = float(_logsumexp(log_alpha[-1]))
        return log_alpha, log_likelihood

    # ------------------------------------------------------------------
    # Backward algorithm (log-space)
    # ------------------------------------------------------------------

    def _backward(self, log_B: np.ndarray) -> np.ndarray:
        """
        Backward pass in log-space.

        Returns
        -------
        log_beta : (T, K)
        """
        T, K = log_B.shape
        log_beta = np.full((T, K), -np.inf)
        log_A = np.log(self._A + 1e-300)

        # t = T-1: beta(T-1) = 1  =>  log_beta = 0
        log_beta[T - 1] = 0.0

        for t in range(T - 2, -1, -1):
            for i in range(K):
                log_beta[t, i] = _logsumexp(log_A[i, :] + log_B[t + 1] + log_beta[t + 1])

        return log_beta

    # ------------------------------------------------------------------
    # Xi computation (log-space)
    # ------------------------------------------------------------------

    def _compute_log_xi(
        self,
        log_alpha: np.ndarray,
        log_beta: np.ndarray,
        log_B: np.ndarray,
    ) -> np.ndarray:
        """
        Compute log xi(t, i, j) for t = 0 .. T-2.

        xi(t, i, j) = alpha(t,i) * A(i,j) * B(j, o_{t+1}) * beta(t+1,j)  /  P(O)

        Returns shape (T-1, K, K).
        """
        T, K = log_alpha.shape
        log_A = np.log(self._A + 1e-300)
        log_xi = np.empty((T - 1, K, K))

        for t in range(T - 1):
            # (K, K) matrix for this time step
            for i in range(K):
                for j in range(K):
                    log_xi[t, i, j] = (
                        log_alpha[t, i]
                        + log_A[i, j]
                        + log_B[t + 1, j]
                        + log_beta[t + 1, j]
                    )
            # normalise over (i, j) so that sum = 1
            norm = _logsumexp(log_xi[t].ravel())
            log_xi[t] -= norm

        return log_xi

    # ------------------------------------------------------------------
    # M-step
    # ------------------------------------------------------------------

    def _maximisation(
        self,
        returns: np.ndarray,
        log_gamma: np.ndarray,
        log_xi: np.ndarray,
    ) -> None:
        """Baum-Welch M-step: re-estimate pi, A, means, variances."""
        T, K = log_gamma.shape
        gamma = np.exp(log_gamma)

        # --- Initial distribution ---
        self._pi = gamma[0] / (gamma[0].sum() + 1e-300)

        # --- Transition matrix ---
        xi = np.exp(log_xi)  # (T-1, K, K)
        xi_sum = xi.sum(axis=0)  # (K, K)
        row_sums = xi_sum.sum(axis=1, keepdims=True)
        self._A = xi_sum / (row_sums + 1e-300)
        # Ensure rows sum to 1
        self._A = np.maximum(self._A, 1e-300)
        self._A /= self._A.sum(axis=1, keepdims=True)

        # --- Emission means and variances ---
        for k in range(K):
            gamma_k = gamma[:, k]
            weight_sum = gamma_k.sum() + 1e-300
            self._means[k] = (gamma_k * returns).sum() / weight_sum
            diff = returns - self._means[k]
            self._vars[k] = (gamma_k * diff ** 2).sum() / weight_sum
            self._vars[k] = max(self._vars[k], _MIN_VARIANCE)

    # ------------------------------------------------------------------
    # Viterbi decoding
    # ------------------------------------------------------------------

    def _viterbi(self, returns: np.ndarray) -> np.ndarray:
        """
        Viterbi algorithm for most-likely state sequence.

        Returns
        -------
        states : (T,) array of state indices (before label re-ordering).
        """
        log_B = self._log_emission_matrix(returns)
        T, K = log_B.shape
        log_A = np.log(self._A + 1e-300)
        log_pi = np.log(self._pi + 1e-300)

        # delta(t, k) = max log-probability of the best path ending in state k at t
        delta = np.full((T, K), -np.inf)
        psi = np.zeros((T, K), dtype=np.int32)

        delta[0] = log_pi + log_B[0]

        for t in range(1, T):
            for j in range(K):
                candidates = delta[t - 1] + log_A[:, j]
                psi[t, j] = int(np.argmax(candidates))
                delta[t, j] = candidates[psi[t, j]] + log_B[t, j]

        # Back-trace
        states = np.empty(T, dtype=np.int32)
        states[T - 1] = int(np.argmax(delta[T - 1]))
        for t in range(T - 2, -1, -1):
            states[t] = psi[t + 1, states[t + 1]]

        return states

    # ------------------------------------------------------------------
    # Regime-conditional statistics
    # ------------------------------------------------------------------

    def _compute_regime_statistics(
        self,
        returns: np.ndarray,
        viterbi_states: np.ndarray,
    ) -> list[RegimeConditionalStats]:
        """Compute per-regime distributional statistics."""
        T = len(returns)
        results: list[RegimeConditionalStats] = []
        trading_days = 252

        for regime_id in range(self.n_states):
            mask = viterbi_states == regime_id
            n_obs = int(mask.sum())
            label = _REGIME_LABELS[regime_id]

            stat = RegimeConditionalStats(
                regime=label,
                num_observations=n_obs,
                fraction_of_time=n_obs / T if T > 0 else 0.0,
            )

            if n_obs > 0:
                r = returns[mask]
                stat.mean_return = float(r.mean())
                stat.volatility = float(r.std(ddof=1)) if n_obs > 1 else 0.0
                stat.annualized_return = float(stat.mean_return * trading_days)
                stat.annualized_volatility = float(stat.volatility * np.sqrt(trading_days))

                if stat.annualized_volatility > 1e-12:
                    stat.sharpe_ratio = float(stat.annualized_return / stat.annualized_volatility)
                else:
                    stat.sharpe_ratio = 0.0

                # Max drawdown within the regime's return sub-series
                stat.max_drawdown = float(self._max_drawdown(r))

            results.append(stat)

        return results

    @staticmethod
    def _max_drawdown(returns: np.ndarray) -> float:
        """Compute maximum drawdown from a returns series."""
        if len(returns) == 0:
            return 0.0
        cumulative = np.cumprod(1.0 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / np.where(running_max > 0, running_max, 1.0)
        return float(np.min(drawdowns))  # most negative value

    # ------------------------------------------------------------------
    # Regime change detection
    # ------------------------------------------------------------------

    def _detect_regime_changes(
        self,
        gamma: np.ndarray,
        window: int = 5,
        threshold: float = 0.30,
    ) -> list[RegimeChangeAlert]:
        """
        Flag days where any regime probability shifted by more than
        *threshold* over the preceding *window* days.
        """
        T, K = gamma.shape
        alerts: list[RegimeChangeAlert] = []
        if T <= window:
            return alerts

        for t in range(window, T):
            prob_now = gamma[t]
            prob_before = gamma[t - window]
            delta = prob_now - prob_before  # signed shift per regime

            for k in range(K):
                if abs(delta[k]) > threshold:
                    # Determine the complementary regime that lost / gained
                    if delta[k] > 0:
                        from_regime_id = int(np.argmin(delta))
                        to_regime_id = k
                    else:
                        from_regime_id = k
                        to_regime_id = int(np.argmax(delta))

                    alerts.append(RegimeChangeAlert(
                        day_index=t,
                        from_regime=_REGIME_LABELS[from_regime_id],
                        to_regime=_REGIME_LABELS[to_regime_id],
                        probability_shift=float(abs(delta[k])),
                        current_probability=float(prob_now[k]),
                    ))
                    break  # one alert per time step is sufficient

        return alerts


# ---------------------------------------------------------------------------
# Log-space utilities (module-level for re-use)
# ---------------------------------------------------------------------------

def _logsumexp(a: np.ndarray) -> float:
    """Numerically stable log-sum-exp of a 1-D array."""
    a = np.asarray(a)
    a_max = a.max()
    if not np.isfinite(a_max):
        return float(a_max)
    return float(a_max + np.log(np.sum(np.exp(a - a_max))))


def _logsumexp_rows(a: np.ndarray) -> np.ndarray:
    """Log-sum-exp across columns for each row of a 2-D array.

    Returns a column vector (T, 1) suitable for broadcasting subtraction.
    """
    a_max = a.max(axis=1, keepdims=True)
    # Guard against rows that are entirely -inf
    finite_mask = np.isfinite(a_max)
    out = np.where(
        finite_mask,
        a_max + np.log(np.sum(np.exp(a - np.where(finite_mask, a_max, 0.0)), axis=1, keepdims=True)),
        a_max,
    )
    return out
