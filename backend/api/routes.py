"""
API Routes — RESTful endpoints exposing all platform capabilities.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, Response
from pydantic import BaseModel

from backend.services.orchestrator import orchestrator
from backend.services.alert_service import alert_service
from backend.services.export_service import export_service
from backend.services.websocket_manager import ws_manager

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
    # Generate alerts from analysis
    analysis_dict = result.to_dict()
    alert_service.evaluate(analysis_dict)
    # Broadcast via WebSocket
    await ws_manager.send_analysis_update(analysis_dict)
    return analysis_dict


# ── Individual Components ──
@router.get("/quote")
async def quote(ticker: str = "UPST"):
    from backend.adapters.provider import data_provider
    env = await data_provider.get_quote(ticker)
    return {"data": env.data, "source": env.source, "quality": env.quality_score}


@router.get("/bars")
async def bars(
    ticker: str = Query("UPST", max_length=10, pattern=r"^[A-Z]{1,5}$"),
    timeframe: str = Query("1d", pattern=r"^(1m|5m|15m|1h|1d|1w)$"),
    days: int = Query(365, ge=1, le=3650),
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


# ── New Engine Endpoints ──
@router.get("/valuation")
async def valuation():
    """Valuation engine — fair value, peer comparison, multiples."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.valuation


@router.get("/funding")
async def funding():
    """Funding analysis — warehouse facilities, capacity, maturity."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.funding


@router.get("/origination")
async def origination():
    """Origination momentum — volume, growth, product mix."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.origination


@router.get("/factor")
async def factor():
    """Factor / style exposure analysis."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.factor


@router.get("/stress")
async def stress():
    """Balance sheet / liquidity stress test."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.stress


@router.get("/reflexivity")
async def reflexivity():
    """Reflexivity / feedback loop analysis."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.reflexivity


@router.get("/execution")
async def execution():
    """Execution / microstructure / liquidity."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.execution


@router.get("/catalyst")
async def catalyst():
    """Catalyst / event analytics."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.catalyst


@router.get("/behavioral")
async def behavioral():
    """Behavioral / crowd psychology analysis."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.behavioral


@router.get("/news-sentiment")
async def news_sentiment():
    """News sentiment analysis."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.news


@router.get("/learning")
async def learning():
    """Learning engine report."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.learning


@router.get("/probability")
async def probability():
    """Probability estimates and cones."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.probability


@router.get("/overfitting")
async def overfitting():
    """Overfitting / false edge detection."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.overfitting


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


# ── Backtest ──
class BacktestRequest(BaseModel):
    strategy: str = "technical_signals"
    days: int = 365
    position_size_pct: float = 10.0
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0


@router.post("/backtest")
async def run_backtest(req: BacktestRequest):
    """Run a backtest with given parameters."""
    return await orchestrator.run_backtest(req.model_dump())


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
async def news(
    ticker: str = Query("UPST", max_length=10, pattern=r"^[A-Z]{1,5}$"),
    limit: int = Query(20, ge=1, le=100),
):
    from backend.adapters.provider import data_provider
    env = await data_provider.get_news(ticker, limit)
    return {"data": env.data, "source": env.source}


# ── Alerts ──
@router.get("/alerts")
async def alerts(
    severity: str | None = Query(None, pattern=r"^(info|warning|critical)$"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get recent system alerts."""
    return {"alerts": alert_service.get_alerts(severity, limit)}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    success = alert_service.acknowledge(alert_id)
    return {"success": success}


# ── Data Quality / Governance ──
@router.get("/data-quality")
async def data_quality():
    """Data governance / quality dashboard."""
    analysis = await orchestrator.run_full_analysis()
    return analysis.data_governance


# ── Export ──
@router.get("/export/csv")
async def export_csv():
    """Export analysis as CSV."""
    analysis = await orchestrator.run_full_analysis()
    csv_data = export_service.to_csv(analysis.to_dict())
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=upst_analysis.csv"},
    )


@router.get("/export/json")
async def export_json():
    """Export analysis as formatted JSON."""
    analysis = await orchestrator.run_full_analysis()
    json_data = export_service.to_json(analysis.to_dict())
    return Response(
        content=json_data,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=upst_analysis.json"},
    )


@router.get("/export/summary")
async def export_summary():
    """Export daily summary as text."""
    analysis = await orchestrator.run_full_analysis()
    summary = export_service.to_summary_text(analysis.to_dict())
    return Response(
        content=summary,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=upst_daily_summary.txt"},
    )


# ── WebSocket ──
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Client can send commands like "subscribe" or "ping"
            if data == "ping":
                await websocket.send_text('{"event":"pong"}')
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)


# ── Scheduler Status ──
@router.get("/scheduler/status")
async def scheduler_status():
    """Get scheduler status."""
    from backend.services.scheduler import scheduler_service
    return scheduler_service.status()
