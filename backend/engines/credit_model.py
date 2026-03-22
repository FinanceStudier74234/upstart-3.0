"""
Structural Credit Model — Merton-style default risk analysis for UPST.
Solves for implied asset value / volatility, computes distance-to-default,
probability of default, credit spreads, Altman Z-Score, credit cycle
sensitivity, and debt maturity stress.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import optimize, stats


@dataclass
class CreditModelResult:
    """Complete structural credit model output."""

    # Merton model
    implied_asset_value: float = 0.0
    implied_asset_volatility: float = 0.0
    distance_to_default: float = 0.0
    probability_of_default: float = 0.0
    merton_iterations: int = 0
    merton_converged: bool = False

    # KMV EDF
    edf_1y: float = 0.0  # 1-year expected default frequency

    # Credit spread
    fair_credit_spread_bps: float = 0.0
    loss_given_default: float = 0.60  # assumed LGD

    # Altman Z-Score
    z_score: float = 0.0
    z_zone: str = ""  # "safe" | "grey" | "distress"
    z_components: dict[str, float] = field(default_factory=dict)

    # Credit cycle sensitivity
    pd_rate_shock: dict[str, float] = field(default_factory=dict)
    # { "+100bp": pd, "+200bp": pd, "-100bp": pd, ... }
    pd_spread_shock: dict[str, float] = field(default_factory=dict)
    pd_funding_stress: dict[str, float] = field(default_factory=dict)

    # Debt maturity stress
    maturity_profile: list[dict] = field(default_factory=list)
    # [ {year, amount, refi_spread_base, refi_spread_stress}, ... ]
    refinancing_risk_score: float = 0.0  # 0..100
    annual_refi_cost_base: float = 0.0
    annual_refi_cost_stress: float = 0.0

    # Summary
    credit_risk_rating: str = ""  # "low" | "moderate" | "elevated" | "high"
    credit_risk_score: float = 50.0  # 0..100


class CreditModelEngine:
    """Structural credit model for UPST default/stress risk."""

    # ── Public entry point ──

    def analyze(
        self,
        market_cap: float,
        equity_vol: float,
        total_debt: float,
        cash: float,
        risk_free_rate: float,
        fundamentals: dict | None = None,
    ) -> CreditModelResult:
        """Run full credit model analysis.

        Parameters
        ----------
        market_cap : float
            Current equity market capitalisation ($M).
        equity_vol : float
            Annualised equity volatility (e.g. 0.65 for 65%).
        total_debt : float
            Total debt outstanding ($M).
        cash : float
            Cash and equivalents ($M).
        risk_free_rate : float
            Risk-free rate (e.g. 0.045 for 4.5%).
        fundamentals : dict | None
            Optional dict with keys used for Altman Z-Score and
            maturity profile:
                working_capital, retained_earnings, ebit, total_equity,
                sales, total_assets, debt_maturities (list[dict]).
        """
        result = CreditModelResult()
        if fundamentals is None:
            fundamentals = {}

        net_debt = max(total_debt - cash, 0.0)

        # 1. Merton structural model
        self._merton_model(
            market_cap, equity_vol, total_debt, risk_free_rate, result
        )

        # 2. KMV EDF
        self._kmv_edf(result)

        # 3. Credit spread estimation
        self._credit_spread(result)

        # 4. Altman Z-Score
        self._altman_z_score(market_cap, total_debt, fundamentals, result)

        # 5. Credit cycle sensitivity
        self._credit_cycle_sensitivity(
            market_cap, equity_vol, total_debt, risk_free_rate, result
        )

        # 6. Debt maturity stress
        self._debt_maturity_stress(
            total_debt, risk_free_rate, fundamentals, result
        )

        # Overall rating
        self._assign_rating(result)

        return result

    # ── 1. Merton structural model ──

    def _merton_model(
        self,
        equity: float,
        equity_vol: float,
        debt: float,
        rf: float,
        result: CreditModelResult,
        T: float = 1.0,
        max_iter: int = 200,
        tol: float = 1e-8,
    ) -> None:
        """Solve for implied asset value V and asset volatility σ_A.

        Equity is a European call on assets:
            E = V N(d1) - D e^{-rT} N(d2)
            σ_E E = σ_A V N(d1)    (Ito's lemma link)

        Newton iteration on (V, σ_A) simultaneously.
        """
        if equity <= 0 or debt <= 0:
            return

        # Initial guesses
        V = equity + debt
        sigma_a = equity_vol * equity / V

        for iteration in range(1, max_iter + 1):
            d1 = self._d1(V, debt, rf, sigma_a, T)
            d2 = d1 - sigma_a * np.sqrt(T)
            Nd1 = stats.norm.cdf(d1)
            Nd2 = stats.norm.cdf(d2)

            # Function values (two equations, two unknowns)
            f1 = V * Nd1 - debt * np.exp(-rf * T) * Nd2 - equity
            f2 = sigma_a * V * Nd1 - equity_vol * equity

            # Check convergence
            if abs(f1) < tol * equity and abs(f2) < tol * equity_vol * equity:
                result.implied_asset_value = round(V, 4)
                result.implied_asset_volatility = round(sigma_a, 6)
                result.merton_iterations = iteration
                result.merton_converged = True
                self._compute_dd_pd(V, debt, rf, sigma_a, T, result)
                return

            # Jacobian (partial derivatives)
            nd1 = stats.norm.pdf(d1)
            dd1_dV = 1.0 / (V * sigma_a * np.sqrt(T))
            dd1_ds = -d1 / sigma_a - np.sqrt(T)

            # ∂f1/∂V, ∂f1/∂σ_A
            j11 = Nd1 + V * nd1 * dd1_dV - debt * np.exp(-rf * T) * nd1 * dd1_dV
            j12 = V * nd1 * dd1_ds - debt * np.exp(-rf * T) * nd1 * (dd1_ds - np.sqrt(T))

            # ∂f2/∂V, ∂f2/∂σ_A
            j21 = sigma_a * (Nd1 + V * nd1 * dd1_dV)
            j22 = V * Nd1 + sigma_a * V * nd1 * dd1_ds

            # Solve 2x2 linear system
            det = j11 * j22 - j12 * j21
            if abs(det) < 1e-20:
                break

            dV = -(j22 * f1 - j12 * f2) / det
            ds = -(-j21 * f1 + j11 * f2) / det

            # Damped update to prevent overshooting
            step_scale = 1.0
            if abs(dV) > 0.5 * V:
                step_scale = min(step_scale, 0.5 * V / abs(dV))
            if abs(ds) > 0.5 * sigma_a:
                step_scale = min(step_scale, 0.5 * sigma_a / abs(ds))

            V += step_scale * dV
            sigma_a += step_scale * ds

            # Enforce positivity
            V = max(V, equity * 0.5)
            sigma_a = max(sigma_a, 0.01)

        # Did not converge — use best estimate
        result.implied_asset_value = round(V, 4)
        result.implied_asset_volatility = round(sigma_a, 6)
        result.merton_iterations = max_iter
        result.merton_converged = False
        self._compute_dd_pd(V, debt, rf, sigma_a, T, result)

    @staticmethod
    def _d1(V: float, D: float, r: float, sigma: float, T: float) -> float:
        return (np.log(V / D) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))

    @staticmethod
    def _compute_dd_pd(
        V: float, D: float, r: float, sigma_a: float, T: float,
        result: CreditModelResult,
    ) -> None:
        dd = (np.log(V / D) + (r - 0.5 * sigma_a**2) * T) / (sigma_a * np.sqrt(T))
        result.distance_to_default = round(float(dd), 4)
        result.probability_of_default = round(float(stats.norm.cdf(-dd)), 6)

    # ── 2. KMV-style EDF ──

    @staticmethod
    def _kmv_edf(result: CreditModelResult) -> None:
        """Expected Default Frequency: PD = N(-DD)."""
        result.edf_1y = round(float(stats.norm.cdf(-result.distance_to_default)), 6)

    # ── 3. Credit spread estimation ──

    @staticmethod
    def _credit_spread(
        result: CreditModelResult, lgd: float = 0.60
    ) -> None:
        """Fair spread = PD * LGD / (1 - PD) in annualised basis points."""
        result.loss_given_default = lgd
        pd = result.probability_of_default
        if pd >= 1.0:
            result.fair_credit_spread_bps = 10000.0
            return
        spread = pd * lgd / max(1 - pd, 1e-12)
        result.fair_credit_spread_bps = round(spread * 10000, 2)  # decimal -> bps

    # ── 4. Altman Z-Score ──

    @staticmethod
    def _altman_z_score(
        market_cap: float,
        total_debt: float,
        fundamentals: dict,
        result: CreditModelResult,
    ) -> None:
        """Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
        X1 = working_capital / total_assets
        X2 = retained_earnings / total_assets
        X3 = EBIT / total_assets
        X4 = market_cap / total_liabilities
        X5 = sales / total_assets
        """
        ta = fundamentals.get("total_assets", 0.0)
        if ta <= 0:
            # Cannot compute without assets; use rough estimate
            ta = market_cap + total_debt

        wc = fundamentals.get("working_capital", 0.0)
        re_ = fundamentals.get("retained_earnings", 0.0)
        ebit = fundamentals.get("ebit", 0.0)
        equity_mv = market_cap
        total_liab = max(total_debt, 1.0)
        sales = fundamentals.get("sales", 0.0)

        x1 = wc / ta
        x2 = re_ / ta
        x3 = ebit / ta
        x4 = equity_mv / total_liab
        x5 = sales / ta

        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

        result.z_score = round(z, 4)
        result.z_components = {
            "x1_wc_ta": round(x1, 4),
            "x2_re_ta": round(x2, 4),
            "x3_ebit_ta": round(x3, 4),
            "x4_mv_equity_tl": round(x4, 4),
            "x5_sales_ta": round(x5, 4),
        }

        if z > 2.99:
            result.z_zone = "safe"
        elif z >= 1.81:
            result.z_zone = "grey"
        else:
            result.z_zone = "distress"

    # ── 5. Credit cycle sensitivity ──

    def _credit_cycle_sensitivity(
        self,
        market_cap: float,
        equity_vol: float,
        total_debt: float,
        rf: float,
        result: CreditModelResult,
    ) -> None:
        """Recompute PD under rate shocks, spread widening, and funding stress."""
        # Rate shocks
        rate_shocks = {
            "-100bp": -0.01,
            "-50bp": -0.005,
            "+50bp": 0.005,
            "+100bp": 0.01,
            "+200bp": 0.02,
            "+300bp": 0.03,
        }
        for label, shock in rate_shocks.items():
            pd = self._pd_under_shock(
                market_cap, equity_vol, total_debt, rf + shock
            )
            result.pd_rate_shock[label] = round(pd, 6)

        # Spread widening (modelled as higher vol + lower equity value)
        spread_shocks = {
            "+50bp": (0.02, 0.95),
            "+100bp": (0.05, 0.90),
            "+200bp": (0.10, 0.82),
            "+500bp": (0.20, 0.65),
        }
        for label, (vol_add, eq_mult) in spread_shocks.items():
            pd = self._pd_under_shock(
                market_cap * eq_mult,
                equity_vol + vol_add,
                total_debt,
                rf,
            )
            result.pd_spread_shock[label] = round(pd, 6)

        # Funding stress (higher debt / lower equity)
        funding_scenarios = {
            "mild": (1.05, 0.95),
            "moderate": (1.15, 0.85),
            "severe": (1.30, 0.70),
            "extreme": (1.50, 0.50),
        }
        for label, (debt_mult, eq_mult) in funding_scenarios.items():
            pd = self._pd_under_shock(
                market_cap * eq_mult,
                equity_vol * 1.1,
                total_debt * debt_mult,
                rf,
            )
            result.pd_funding_stress[label] = round(pd, 6)

    def _pd_under_shock(
        self,
        equity: float,
        equity_vol: float,
        debt: float,
        rf: float,
        T: float = 1.0,
    ) -> float:
        """Quick PD calculation under modified parameters.

        Uses a simplified iterative solve (fewer iterations) to keep
        sensitivity analysis fast.
        """
        if equity <= 0 or debt <= 0:
            return 1.0

        V = equity + debt
        sigma_a = equity_vol * equity / V

        for _ in range(50):
            d1 = self._d1(V, debt, rf, sigma_a, T)
            Nd1 = stats.norm.cdf(d1)
            d2 = d1 - sigma_a * np.sqrt(T)
            Nd2 = stats.norm.cdf(d2)

            V_new = (equity + debt * np.exp(-rf * T) * Nd2) / max(Nd1, 1e-12)
            sigma_new = equity_vol * equity / max(V_new * Nd1, 1e-12)

            if abs(V_new - V) < 1e-6 * V and abs(sigma_new - sigma_a) < 1e-6:
                V, sigma_a = V_new, sigma_new
                break
            V, sigma_a = V_new, max(sigma_new, 0.01)

        dd = (np.log(V / debt) + (rf - 0.5 * sigma_a**2) * T) / (
            sigma_a * np.sqrt(T)
        )
        return float(stats.norm.cdf(-dd))

    # ── 6. Debt maturity stress ──

    @staticmethod
    def _debt_maturity_stress(
        total_debt: float,
        rf: float,
        fundamentals: dict,
        result: CreditModelResult,
    ) -> None:
        """Map debt maturities and simulate refinancing risk under
        different spread scenarios."""
        maturities = fundamentals.get("debt_maturities", None)
        if not maturities:
            # Assume a stylised profile if none provided
            maturities = [
                {"year": 1, "amount": total_debt * 0.20},
                {"year": 2, "amount": total_debt * 0.25},
                {"year": 3, "amount": total_debt * 0.25},
                {"year": 4, "amount": total_debt * 0.15},
                {"year": 5, "amount": total_debt * 0.15},
            ]

        base_spread_bps = max(result.fair_credit_spread_bps, 50.0)
        stress_spread_bps = base_spread_bps * 2.5  # 2.5x widening

        profile: list[dict] = []
        total_refi_base = 0.0
        total_refi_stress = 0.0
        weighted_urgency = 0.0
        total_amount = 0.0

        for mat in maturities:
            year = mat.get("year", 1)
            amount = mat.get("amount", 0.0)
            if amount <= 0:
                continue

            # Refinancing cost = amount * (rf + spread)
            refi_base = amount * (rf + base_spread_bps / 10000)
            refi_stress = amount * (rf + stress_spread_bps / 10000)

            profile.append(
                {
                    "year": year,
                    "amount": round(amount, 2),
                    "refi_spread_base_bps": round(base_spread_bps, 2),
                    "refi_spread_stress_bps": round(stress_spread_bps, 2),
                    "annual_cost_base": round(refi_base, 2),
                    "annual_cost_stress": round(refi_stress, 2),
                }
            )

            total_refi_base += refi_base
            total_refi_stress += refi_stress

            # Near-term maturities are more urgent
            urgency = amount / max(year, 0.5)
            weighted_urgency += urgency
            total_amount += amount

        result.maturity_profile = profile
        result.annual_refi_cost_base = round(total_refi_base, 2)
        result.annual_refi_cost_stress = round(total_refi_stress, 2)

        # Refinancing risk score (0=safe, 100=high risk)
        # Based on near-term concentration and spread levels
        if total_amount > 0:
            concentration = weighted_urgency / total_amount  # higher if front-loaded
            spread_factor = min(base_spread_bps / 500, 1.0)
            raw_score = (concentration * 40 + spread_factor * 60)
            result.refinancing_risk_score = round(min(max(raw_score, 0), 100), 2)

    # ── Overall rating ──

    @staticmethod
    def _assign_rating(result: CreditModelResult) -> None:
        """Combine PD, Z-Score, and refi risk into an overall credit rating."""
        pd = result.probability_of_default
        z = result.z_score
        refi = result.refinancing_risk_score

        # Score: lower PD, higher Z, lower refi risk = better
        # PD contribution (0-40 points, lower PD = more points)
        if pd < 0.005:
            pd_score = 90
        elif pd < 0.02:
            pd_score = 75
        elif pd < 0.05:
            pd_score = 60
        elif pd < 0.10:
            pd_score = 40
        elif pd < 0.20:
            pd_score = 25
        else:
            pd_score = 10

        # Z-Score contribution
        if z > 3.0:
            z_score_pts = 90
        elif z > 2.5:
            z_score_pts = 75
        elif z > 1.81:
            z_score_pts = 55
        elif z > 1.2:
            z_score_pts = 35
        else:
            z_score_pts = 15

        # Refi risk contribution (invert: low refi_risk = high score)
        refi_score = max(100 - refi, 0)

        composite = 0.45 * pd_score + 0.30 * z_score_pts + 0.25 * refi_score
        result.credit_risk_score = round(composite, 2)

        if composite >= 75:
            result.credit_risk_rating = "low"
        elif composite >= 55:
            result.credit_risk_rating = "moderate"
        elif composite >= 35:
            result.credit_risk_rating = "elevated"
        else:
            result.credit_risk_rating = "high"
