import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
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

      {/* Intraday Volume Profile Chart */}
      {e.intraday_pattern && Object.keys(e.intraday_pattern).length > 0 && (
        <Panel title="Intraday Volume Profile">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={Object.entries(e.intraday_pattern).map(([period, pct]) => ({
              period, pct: typeof pct === 'number' ? pct * 100 : 0,
            }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="period" tick={{ fontSize: 9, fill: '#9ca3af' }} />
              <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} tickFormatter={v => `${v}%`} />
              <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
                formatter={v => [`${v.toFixed(1)}%`, 'Volume Share']} />
              <Bar dataKey="pct" fill="#06b6d4" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {/* Slippage Comparison Chart */}
      {(e.slippage_100 != null || e.slippage_1000 != null) && (
        <Panel title="Estimated Slippage by Size">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={[
              { size: '100 sh', slippage: (e.slippage_100 || 0) * 100 },
              { size: '1K sh', slippage: (e.slippage_1000 || 0) * 100 },
              { size: '10K sh', slippage: (e.slippage_10000 || 0) * 100 },
            ]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="size" tick={{ fontSize: 10, fill: '#9ca3af' }} />
              <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} tickFormatter={v => `${v}%`} />
              <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
                formatter={v => [`${v.toFixed(3)}%`, 'Slippage']} />
              <Bar dataKey="slippage" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      <ScoreBar label="Liquidity Score" value={e.liquidity_score} />
    </div>
  )
}
