import React, { useState } from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import useStore from '../../stores/useStore'

const SLIDERS = [
  { key: 'spy_return_pct', label: 'SPY Return %', min: -30, max: 30, step: 1 },
  { key: 'fed_funds_change_bps', label: 'Fed Funds Chg (bps)', min: -200, max: 200, step: 25 },
  { key: 'treasury_10y_change_bps', label: '10Y Yield Chg (bps)', min: -200, max: 200, step: 25 },
  { key: 'origination_growth_change_pct', label: 'Origination Growth %', min: -50, max: 50, step: 5 },
  { key: 'funding_capacity_change_pct', label: 'Funding Capacity %', min: -75, max: 50, step: 5 },
  { key: 'valuation_multiple_change_pct', label: 'Valuation Multiple %', min: -50, max: 50, step: 5 },
  { key: 'iv_change_pct', label: 'IV Change %', min: -50, max: 100, step: 5 },
  { key: 'squeeze_risk_change_pct', label: 'Squeeze Risk Change %', min: -30, max: 50, step: 5 },
  { key: 'macro_stress_shock', label: 'Macro Stress (0-1)', min: 0, max: 1, step: 0.1 },
  { key: 'credit_deterioration_shock', label: 'Credit Stress (0-1)', min: 0, max: 1, step: 0.1 },
  { key: 'world_risk_shock', label: 'World Risk (0-1)', min: 0, max: 1, step: 0.1 },
  { key: 'news_sentiment_shock', label: 'News Sentiment (-1 to 1)', min: -1, max: 1, step: 0.1 },
]

export default function ScenarioLab() {
  const { runScenario, scenarioResult, loading } = useStore()
  const [params, setParams] = useState(
    Object.fromEntries(SLIDERS.map(s => [s.key, 0]))
  )

  const handleChange = (key, value) => {
    setParams(p => ({ ...p, [key]: parseFloat(value) }))
  }

  const handleRun = () => runScenario(params)

  const r = scenarioResult

  return (
    <div className="space-y-4">
      <Panel title="Interactive Scenario Lab">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {SLIDERS.map(s => (
            <div key={s.key} className="space-y-1">
              <div className="flex justify-between text-[10px]">
                <span className="text-terminal-muted">{s.label}</span>
                <span className="font-bold">{params[s.key]}</span>
              </div>
              <input
                type="range"
                min={s.min} max={s.max} step={s.step}
                value={params[s.key]}
                onChange={e => handleChange(s.key, e.target.value)}
                className="w-full h-1 accent-terminal-cyan"
              />
            </div>
          ))}
        </div>
        <button onClick={handleRun} disabled={loading} className="btn-primary mt-4">
          {loading ? 'Running...' : 'Run Scenario'}
        </button>
      </Panel>

      {r && (
        <Panel title="Scenario Results">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Stat label="Adjusted Price" value={`$${r.adjusted_price_target?.toFixed(2)}`}
              color={r.adjusted_price_target > (r.inputs?.spy_return_pct || 0) ? 'text-terminal-green' : 'text-terminal-red'} />
            <Stat label="P(Up)" value={`${((r.probability_up || 0) * 100).toFixed(0)}%`} />
            <Stat label="P(Down)" value={`${((r.probability_down || 0) * 100).toFixed(0)}%`} />
            <Stat label="SPY Impact" value={`${r.spy_adjusted_expected_move?.toFixed(1)}%`} />
            <Stat label="Confidence" value={r.confidence?.toFixed(0)} />
            <Stat label="Fragility" value={r.fragility?.toFixed(0)} />
            <Stat label="Recommendation" value={r.adjusted_trade_recommendation?.toUpperCase()} />
            <Stat label="Position Size" value={`${r.adjusted_position_size_pct?.toFixed(1)}%`} />
          </div>
          {r.explanation && (
            <div className="p-2 bg-terminal-bg rounded text-[10px] text-terminal-muted">{r.explanation}</div>
          )}
          {r.adjusted_risk_metrics && (
            <div className="mt-2 grid grid-cols-3 gap-2 text-[10px]">
              <div>VaR 95%: ${r.adjusted_risk_metrics.var_95?.toFixed(2)}</div>
              <div>CVaR 95%: ${r.adjusted_risk_metrics.cvar_95?.toFixed(2)}</div>
              <div>Price Chg: {r.adjusted_risk_metrics.price_change_pct?.toFixed(1)}%</div>
            </div>
          )}
          {r.adjusted_scores && (
            <div className="mt-3 grid grid-cols-2 md:grid-cols-3 gap-1 text-[10px]">
              {Object.entries(r.adjusted_scores).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-terminal-muted">{k.replace(/_/g, ' ')}</span>
                  <span className="font-bold">{typeof v === 'number' ? v.toFixed(0) : v}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}
    </div>
  )
}
