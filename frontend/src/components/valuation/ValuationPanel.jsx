import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  Cell, ReferenceLine,
} from 'recharts'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function ValuationPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const v = analysis.valuation || {}

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="P/S" value={v.price_to_sales?.toFixed(1)} /></Panel>
        <Panel><Stat label="EV/Rev" value={v.ev_revenue?.toFixed(1)} /></Panel>
        <Panel><Stat label="EV/EBITDA" value={v.ev_ebitda?.toFixed(1)} /></Panel>
        <Panel><Stat label="P/B" value={v.price_to_book?.toFixed(1)} /></Panel>
        <Panel><Stat label="FCF Yield" value={v.fcf_yield ? `${v.fcf_yield}%` : '--'} color={v.fcf_yield > 0 ? 'text-terminal-green' : 'text-terminal-red'} /></Panel>
        <Panel><Stat label="Growth" value={v.growth_rate ? `${v.growth_rate}%` : '--'} /></Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel title="Fair Value Scenarios" className="col-span-1 lg:col-span-2">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-terminal-red text-[10px]">BEAR</div>
              <div className="text-xl font-bold">{v.fair_value_bear ? `$${v.fair_value_bear}` : '--'}</div>
              <div className="text-[10px] text-terminal-muted">4x fwd P/S</div>
            </div>
            <div>
              <div className="text-terminal-amber text-[10px]">BASE</div>
              <div className="text-2xl font-black text-terminal-cyan">{v.fair_value_base ? `$${v.fair_value_base}` : '--'}</div>
              <div className="text-[10px] text-terminal-muted">7x fwd P/S</div>
            </div>
            <div>
              <div className="text-terminal-green text-[10px]">BULL</div>
              <div className="text-xl font-bold">{v.fair_value_bull ? `$${v.fair_value_bull}` : '--'}</div>
              <div className="text-[10px] text-terminal-muted">10x fwd P/S</div>
            </div>
          </div>
          {v.upside_to_fair != null && (
            <div className="mt-3 text-center text-xs">
              <span className="text-terminal-muted">Upside to Fair Value: </span>
              <span className={v.upside_to_fair > 0 ? 'text-terminal-green font-bold' : 'text-terminal-red font-bold'}>
                {v.upside_to_fair > 0 ? '+' : ''}{v.upside_to_fair}%
              </span>
            </div>
          )}
        </Panel>

        <Panel title="Historical Context">
          <div className="space-y-2 text-xs">
            <div><span className="text-terminal-muted">P/S 3Y Median:</span> {v.ps_median_3y?.toFixed(1)}x</div>
            <div><span className="text-terminal-muted">P/S Percentile:</span> {v.ps_percentile?.toFixed(0)}%</div>
            <div><span className="text-terminal-muted">PEG-like:</span> {v.peg_like_ratio?.toFixed(2)}</div>
            <div><span className="text-terminal-muted">DCF Value:</span> {v.dcf_value ? `$${v.dcf_value}` : '--'}</div>
            <div><span className="text-terminal-muted">vs Peer Median:</span>
              <span className={v.vs_peer_median > 0 ? 'text-terminal-red' : 'text-terminal-green'}>
                {' '}{v.vs_peer_median > 0 ? '+' : ''}{v.vs_peer_median?.toFixed(1)}%
              </span>
            </div>
          </div>
        </Panel>
      </div>

      {/* Fair Value Bridge Chart */}
      {(v.fair_value_bear || v.fair_value_base || v.fair_value_bull) && (
        <Panel title="Valuation Bridge">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={[
              { scenario: 'Bear', value: v.fair_value_bear || 0 },
              { scenario: 'Base', value: v.fair_value_base || 0 },
              { scenario: 'Bull', value: v.fair_value_bull || 0 },
            ]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="scenario" tick={{ fontSize: 10, fill: '#9ca3af' }} />
              <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} tickFormatter={v => `$${v}`} domain={[0, 'auto']} />
              <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
                formatter={val => [`$${val.toFixed(2)}`, 'Fair Value']} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                <Cell fill="#ef4444" />
                <Cell fill="#06b6d4" />
                <Cell fill="#10b981" />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {/* Peer Comparison Chart */}
      <Panel title="Peer Comparison">
        {(v.peer_multiples || []).length > 0 && (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={[
              { ticker: 'UPST', ps: v.price_to_sales || 0, ev_rev: v.ev_revenue || 0 },
              ...(v.peer_multiples || []).map(p => ({ ticker: p.ticker, ps: p.ps || 0, ev_rev: p.ev_rev || 0 })),
            ]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="ticker" tick={{ fontSize: 10, fill: '#9ca3af' }} />
              <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} tickFormatter={v => `${v}x`} />
              <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
                formatter={val => [`${val.toFixed(1)}x`]} />
              <Bar dataKey="ps" fill="#06b6d4" name="P/S" radius={[3, 3, 0, 0]} />
              <Bar dataKey="ev_rev" fill="#8b5cf6" name="EV/Rev" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-terminal-muted border-b border-terminal-border">
                <th className="text-left py-1">Ticker</th>
                <th className="text-right">P/S</th>
                <th className="text-right">EV/Rev</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-terminal-border bg-terminal-panel/50">
                <td className="py-1 font-bold text-terminal-cyan">UPST</td>
                <td className="text-right font-bold">{v.price_to_sales?.toFixed(1)}x</td>
                <td className="text-right font-bold">{v.ev_revenue?.toFixed(1)}x</td>
              </tr>
              {(v.peer_multiples || []).map((p, i) => (
                <tr key={i} className="border-b border-terminal-border/30">
                  <td className="py-1">{p.ticker}</td>
                  <td className="text-right">{p.ps?.toFixed(1)}x</td>
                  <td className="text-right">{p.ev_rev?.toFixed(1)}x</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <ScoreBar label="Valuation Attractiveness" value={v.valuation_attractiveness_score} />
    </div>
  )
}
