import React, { useState } from 'react'
import Panel from '../common/Panel'
import useStore from '../../stores/useStore'

const BOTS = [
  { name: 'price_action', label: 'Price Action Sim', defaultParams: { n_paths: 1000, horizon_days: 63, volatility: 0.65, drift: 0, beta: 1.5, spy_return_pct: 0 } },
  { name: 'squeeze', label: 'Squeeze Simulator', defaultParams: { short_pct_float: 15, days_to_cover: 3, utilization: 70, call_oi_surge_pct: 0, trigger_move_pct: 5 } },
  { name: 'macro_shock', label: 'Macro Shock', defaultParams: { beta: 1.5 } },
  { name: 'funding_stress', label: 'Funding Stress', defaultParams: { total_capacity_mm: 5000, facility_count: 8, avg_maturity_months: 18, quarterly_origination_mm: 2000 } },
  { name: 'strategy', label: 'Options Strategy', defaultParams: { iv: 0.7, dte: 30, direction: 'bearish' } },
  { name: 'options_reaction', label: 'Options Reaction', defaultParams: { price_change_pct: -10, iv_change_pct: 20, days_elapsed: 7, base_iv: 0.7 } },
  { name: 'regime', label: 'Regime Transition', defaultParams: { current_regime: 'normal', vix: 18, spy_trend: 'neutral', credit_spread_bps: 350 } },
  { name: 'trade_decision', label: 'Trade Decision', defaultParams: {} },
]

export default function BotLab() {
  const { runBot, botResult, loading } = useStore()
  const [selectedBot, setSelectedBot] = useState(BOTS[0])
  const [params, setParams] = useState(BOTS[0].defaultParams)

  const handleSelect = (bot) => {
    setSelectedBot(bot)
    setParams(bot.defaultParams)
  }

  const handleParamChange = (key, value) => {
    setParams(p => ({ ...p, [key]: isNaN(Number(value)) ? value : Number(value) }))
  }

  return (
    <div className="space-y-4">
      <Panel title="Simulation Bot Lab">
        <div className="flex flex-wrap gap-2 mb-4">
          {BOTS.map(b => (
            <button key={b.name} onClick={() => handleSelect(b)}
              className={`text-[10px] px-2 py-1 rounded ${selectedBot.name === b.name ? 'bg-terminal-cyan text-terminal-bg' : 'bg-terminal-bg text-terminal-muted hover:text-terminal-text'}`}>
              {b.label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
          {Object.entries(params).map(([k, v]) => (
            <div key={k} className="space-y-1">
              <label className="text-[10px] text-terminal-muted">{k.replace(/_/g, ' ')}</label>
              <input
                type={typeof v === 'number' ? 'number' : 'text'}
                value={v}
                onChange={e => handleParamChange(k, e.target.value)}
                className="w-full bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-xs text-terminal-text"
                step={typeof v === 'number' && v < 1 ? 0.01 : 1}
              />
            </div>
          ))}
        </div>

        <button onClick={() => runBot(selectedBot.name, params)} disabled={loading} className="btn-primary">
          {loading ? 'Running...' : `Run ${selectedBot.label}`}
        </button>
      </Panel>

      {botResult && (
        <Panel title={`${botResult.bot_name || selectedBot.label} Results`}>
          <div className="text-xs mb-2">{botResult.explanation}</div>
          <div className="text-[10px] text-terminal-muted mb-2">Confidence: {((botResult.confidence || 0) * 100).toFixed(0)}%</div>

          {botResult.results && (
            <pre className="bg-terminal-bg rounded p-3 text-[10px] overflow-auto max-h-96">
              {JSON.stringify(botResult.results, null, 2)}
            </pre>
          )}

          {botResult.limitations?.length > 0 && (
            <div className="mt-2 text-[10px] text-terminal-amber">
              <strong>Limitations:</strong> {botResult.limitations.join('; ')}
            </div>
          )}

          {botResult.is_simulation && (
            <div className="mt-2 text-[10px] text-terminal-amber border border-terminal-amber rounded px-2 py-1">
              SIMULATION MODE — Not connected to live trading
            </div>
          )}
        </Panel>
      )}
    </div>
  )
}
