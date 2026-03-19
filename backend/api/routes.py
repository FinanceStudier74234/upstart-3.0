"""
API Routes — Phase 8
RESTful endpoints exposing all platform capabilities.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.services.orchestrator import orchestrator

router = APIRouter(prefix="/api/v1", tags=["UPST Hub"])


# ── Health ──
@router.get("/health")
async def health():
    return {"status": "ok", "system": "UPST Quant Finance Hub v3.0"}


# ── Full Analysis ──
@router.get("/analysis")
async def full_analysis():
    """Run complete analysis pipeline and return all engine outputs."""
    result = await orchestrator.run_full_analysis()
    return result.to_dict()


# ── Individual Components ──
@router.get("/quote")
async def quote(ticker: str = "UPST"):
    from backend.adapters.provider import data_provider
    env = await data_provider.get_quote(ticker)
    return {"data": env.data, "source": env.source, "quality": env.quality_score}


@router.get("/bars")
async def bars(
    ticker: str = "UPST",
    timeframe: str = "1d",
    days: int = 365,
):
    import datetime as dt
    from backend.adapters.provider import data_provider
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    env = await data_provider.get_bars(ticker, timeframe, start, end)
    return {"data": env.data, "source": env.source, "count": len(env.data) if env.data else 0}


@router.get("/technical")
async def technical(ticker: str = "UPST"):
    """Technical analysis snapshot."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.technical


@router.get("/options")
async def options_chain(ticker: str = "UPST"):
    """Options / volatility analysis."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.options


@router.get("/short")
async def short_analysis():
    """Short-selling / squeeze intelligence."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.short


@router.get("/spy-relationship")
async def spy_relationship():
    """SPY / beta / market relationship."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.spy_relationship


@router.get("/scores")
async def scores():
    """All 15 mandatory scores."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.scores


@router.get("/trade-decision")
async def trade_decision():
    """Trade decision with full explanation."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.trade_decision


@router.get("/forecast")
async def forecast():
    """Multi-model ensemble forecast."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.forecast


@router.get("/risk")
async def risk_metrics():
    """Risk metrics and position sizing."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.risk


# ── Scenario Lab ──
class ScenarioRequest(BaseModel):
    spy_return_pct: float = 0.0
    spy_drawdown_pct: float = 0.0
    beta_override: float | None = None
    fed_funds_change_bps: float = 0.0
    treasury_10y_change_bps: float = 0.0
    origination_growth_change_pct: float = 0.0
    funding_capacity_change_pct: float = 0.0
    ebitda_margin_change_pct: float = 0.0
    valuation_multiple_change_pct: float = 0.0
    iv_change_pct: float = 0.0
    short_interest_change_pct: float = 0.0
    squeeze_risk_change_pct: float = 0.0
    macro_stress_shock: float = 0.0
    credit_deterioration_shock: float = 0.0
    world_risk_shock: float = 0.0
    news_sentiment_shock: float = 0.0
    options_flow_shock: float = 0.0


@router.post("/scenario")
async def run_scenario(req: ScenarioRequest):
    """Interactive scenario lab — adjust levers and get recalculated outputs."""
    return await orchestrator.run_scenario(req.model_dump())


# ── Simulation Bots ──
class BotRequest(BaseModel):
    bot_name: str
    params: dict = {}


@router.post("/bot")
async def run_bot(req: BotRequest):
    """Run a simulation bot with custom parameters."""
    return await orchestrator.run_bot(req.bot_name, req.params)


@router.get("/bots")
async def list_bots():
    """List available simulation bots."""
    return {
        "bots": [
            {"name": "price_action", "description": "Price path simulation via Monte Carlo"},
            {"name": "options_reaction", "description": "Options chain repricing simulator"},
            {"name": "squeeze", "description": "Short squeeze cascade simulator"},
            {"name": "funding_stress", "description": "Funding loss / capacity reduction simulator"},
            {"name": "macro_shock", "description": "Macro scenario impact simulator"},
            {"name": "strategy", "description": "Options strategy P/L comparison"},
            {"name": "trade_decision", "description": "Virtual trading assistant"},
            {"name": "regime", "description": "Market regime transition simulator"},
        ]
    }


# ── Macro ──
@router.get("/macro/{indicator}")
async def macro_indicator(indicator: str):
    from backend.adapters.provider import data_provider
    env = await data_provider.get_macro(indicator)
    return {"data": env.data, "source": env.source}


# ── News ──
@router.get("/news")
async def news(ticker: str = "UPST", limit: int = 20):
    from backend.adapters.provider import data_provider
    env = await data_provider.get_news(ticker, limit)
    return {"data": env.data, "source": env.source}


# ── Alerts ──
@router.get("/alerts")
async def alerts():
    """Get recent system alerts."""
    # TODO: Wire to persistent alert storage
    return {"alerts": [], "count": 0}


# ── Data Quality ──
@router.get("/data-quality")
async def data_quality():
    """Data governance / quality dashboard."""
    analysis = await orchestrator.run_full_analysis()
    return {
        "sources": analysis.data_sources,
        "warnings": analysis.warnings,
        "freshness": {k: "live" for k in analysis.data_sources},
    }
