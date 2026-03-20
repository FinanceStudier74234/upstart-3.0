import React from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function ExecutionPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const e = analysis.execution || {}

  const spreadColor = (val) => {
    if (val == null) return ''
    return val < 0.1 ? 'text-terminal-green' : val < 0.3 ? 'text-terminal-amber' : 'text-terminal-red'
  }

  return (
    <div className="space-y-4">
      {/* Core Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="Bid" value={e.bid ? `$${e.bid.toFixed(2)}` : '--'} /></Panel>
        <Panel><Stat label="Ask" value={e.ask ? `$${e.ask.toFixed(2)}` : '--'} /></Panel>
        <Panel><Stat label="Spread" value={e.spread_pct ? `${e.spread_pct.toFixed(3)}%` : '--'}
          color={spreadColor(e.spread_pct)} /></Panel>
        <Panel><Stat label="ADV (30d)" value={e.adv_30d ? `${(e.adv_30d / 1e6).toFixed(1)}M` : '--'} /></Panel>
        <Panel><Stat label="Depth Imbalance" value={e.depth_imbalance?.toFixed(2)}
          color={Math.abs(e.depth_imbalance) > 0.3 ? 'text-terminal-amber' : ''} /></Panel>
        <Panel><Stat label="Liquidity Regime" value={e.liquidity_regime || '--'}
          color={e.liquidity_regime === 'thin' ? 'text-terminal-red' :
                 e.liquidity_regime === 'deep' ? 'text-terminal-green' : ''} /></Panel>
      </div>

      {/* Slippage & Impact */}
      <Panel title="Market Impact & Slippage">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="p-2 bg-terminal-bg rounded text-xs">
            <div className="text-terminal-muted mb-1">Est. Slippage (100 shares)</div>
            <div className="text-terminal-text font-bold">
              {e.slippage_100 != null ? `${(e.slippage_100 * 100).toFixed(2)}%` : '--'}
            </div>
          </div>
          <div className="p-2 bg-terminal-bg rounded text-xs">
            <div className="text-terminal-muted mb-1">Est. Slippage (1000 shares)</div>
            <div className="text-terminal-text font-bold">
              {e.slippage_1000 != null ? `${(e.slippage_1000 * 100).toFixed(2)}%` : '--'}
            </div>
          </div>
          <div className="p-2 bg-terminal-bg rounded text-xs">
            <div className="text-terminal-muted mb-1">Est. Slippage (10000 shares)</div>
            <div className="text-terminal-text font-bold">
              {e.slippage_10000 != null ? `${(e.slippage_10000 * 100).toFixed(2)}%` : '--'}
            </div>
          </div>
          <div className="p-2 bg-terminal-bg rounded text-xs">
            <div className="text-terminal-muted mb-1">Sqrt Impact Coeff</div>
            <div className="text-terminal-text font-bold">
              {e.sqrt_impact_coeff?.toFixed(4) || '--'}
            </div>
          </div>
        </div>
      </Panel>

      {/* Optimal Execution */}
      <Panel title="Optimal Execution Strategy">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="p-2 bg-terminal-bg rounded text-xs">
            <div className="text-terminal-muted mb-1">Recommended Algo</div>
            <div className="text-terminal-cyan font-bold text-sm">{e.optimal_algo || 'TWAP'}</div>
          </div>
          <div className="p-2 bg-terminal-bg rounded text-xs">
            <div className="text-terminal-muted mb-1">Max Participation Rate</div>
            <div className="text-terminal-text font-bold">
              {e.max_participation_rate ? `${(e.max_participation_rate * 100).toFixed(0)}%` : '--'}
            </div>
          </div>
          <div className="p-2 bg-terminal-bg rounded text-xs">
            <div className="text-terminal-muted mb-1">Urgency</div>
            <div className="text-terminal-text font-bold">{e.urgency || 'Normal'}</div>
          </div>
          <div className="p-2 bg-terminal-bg rounded text-xs">
            <div className="text-terminal-muted mb-1">Best Window</div>
            <div className="text-terminal-text font-bold">{e.best_execution_window || '10:00-15:00'}</div>
          </div>
        </div>
      </Panel>

      {/* Intraday Patterns */}
      {e.intraday_pattern && (
        <Panel title="Intraday Volume Pattern">
          <div className="grid grid-cols-4 gap-2 text-xs">
            {Object.entries(e.intraday_pattern).map(([period, pct]) => (
              <div key={period} className="p-2 bg-terminal-bg rounded">
                <div className="text-terminal-muted mb-1">{period}</div>
                <div className="text-terminal-text font-bold">
                  {typeof pct === 'number' ? `${(pct * 100).toFixed(0)}%` : pct}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <ScoreBar label="Liquidity Score" value={e.liquidity_score} />
    </div>
  )
}
