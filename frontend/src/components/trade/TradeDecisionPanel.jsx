import React from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  BarChart, Bar, ReferenceLine, Cell,
} from 'recharts'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function TradeDecisionPanel({ analysis }) {
  if (!analysis) return (
    <div className="space-y-4">
      <div className="panel p-6 animate-pulse text-center">
        <div className="h-10 bg-terminal-border/30 rounded w-32 mx-auto mb-3" />
        <div className="h-4 bg-terminal-border/30 rounded w-24 mx-auto" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="panel p-3 animate-pulse">
            <div className="h-3 bg-terminal-border/30 rounded w-16 mb-2" />
            <div className="h-6 bg-terminal-border/30 rounded w-12" />
          </div>
        ))}
      </div>
    </div>
  )
  const d = analysis.trade_decision || {}
  const prob = analysis.probability || {}

  const actionColor = (d.action || '').includes('buy') ? 'text-terminal-green' :
    (d.action || '').includes('short') ? 'text-terminal-red' : 'text-terminal-amber'

  return (
    <div className="space-y-4">
      <div className="text-center py-4">
        <div className={`text-4xl font-black ${actionColor}`}>{d.action?.toUpperCase() || 'HOLD'}</div>
        <div className="text-terminal-muted text-sm mt-1">{d.vehicle}</div>
        <div className="text-terminal-muted text-xs">{d.confidence} confidence</div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="Entry" value={d.entry_price ? `$${d.entry_price.toFixed(2)}` : '--'} /></Panel>
        <Panel><Stat label="Target" value={d.target_price ? `$${d.target_price.toFixed(2)}` : '--'} color="text-terminal-green" /></Panel>
        <Panel><Stat label="Stop" value={d.stop_price ? `$${d.stop_price.toFixed(2)}` : '--'} color="text-terminal-red" /></Panel>
        <Panel><Stat label="R:R Ratio" value={d.reward_risk_ratio?.toFixed(2)} /></Panel>
        <Panel><Stat label="Position %" value={d.suggested_position_pct ? `${d.suggested_position_pct.toFixed(1)}%` : '--'} /></Panel>
        <Panel><Stat label="Timeframe" value={d.timeframe || '--'} /></Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Decision Rationale">
          <div className="text-xs text-terminal-muted leading-relaxed">{d.explanation}</div>
          {d.what_would_change && (
            <div className="mt-2 p-2 bg-terminal-bg rounded text-terminal-amber text-[10px]">
              <strong>What Would Change:</strong> {d.what_would_change}
            </div>
          )}
        </Panel>

        <Panel title="Risk Factors">
          {d.risk_factors?.length > 0 ? (
            <ul className="space-y-1 text-xs text-terminal-red">
              {d.risk_factors.map((r, i) => <li key={i}>- {r}</li>)}
            </ul>
          ) : <div className="text-xs text-terminal-muted">No significant risk factors</div>}
        </Panel>
      </div>

      <Panel title="Probability Estimates">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <Stat label="P(Up 1W)" value={prob.prob_up_1w ? `${(prob.prob_up_1w * 100).toFixed(0)}%` : '--'} />
          <Stat label="P(Up 1M)" value={prob.prob_up_1m ? `${(prob.prob_up_1m * 100).toFixed(0)}%` : '--'} />
          <Stat label="P(Up 3M)" value={prob.prob_up_3m ? `${(prob.prob_up_3m * 100).toFixed(0)}%` : '--'} />
          <Stat label="P(>Target)" value={prob.prob_above_target ? `${(prob.prob_above_target * 100).toFixed(0)}%` : '--'} />
          <Stat label="P(<Stop)" value={prob.prob_below_stop ? `${(prob.prob_below_stop * 100).toFixed(0)}%` : '--'} color="text-terminal-red" />
          <Stat label="P(>5% 1W)" value={prob.prob_move_gt_5pct_1w ? `${(prob.prob_move_gt_5pct_1w * 100).toFixed(0)}%` : '--'} />
          <Stat label="P(Squeeze)" value={prob.prob_squeeze ? `${(prob.prob_squeeze * 100).toFixed(0)}%` : '--'} />
          <Stat label="Confidence" value={prob.overall_confidence?.toFixed(0)} />
        </div>
      </Panel>

      {prob.cone_1m && Object.keys(prob.cone_1m).length > 0 && (
        <Panel title="Probability Cones (1 Month)">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={Object.entries(prob.cone_1m).map(([k, v]) => ({ level: k.toUpperCase(), price: v }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="level" tick={{ fontSize: 10, fill: '#9ca3af' }} />
              <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} domain={['auto', 'auto']}
                tickFormatter={v => `$${v}`} />
              <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
                formatter={v => [`$${v?.toFixed(2)}`, 'Price']} />
              {d.entry_price && <ReferenceLine y={d.entry_price} stroke="#06b6d4" strokeDasharray="3 3"
                label={{ value: 'Entry', fill: '#06b6d4', fontSize: 9 }} />}
              <Bar dataKey="price" radius={[4, 4, 0, 0]}>
                {Object.entries(prob.cone_1m).map(([k], i) => (
                  <Cell key={i} fill={k.includes('p10') || k.includes('p25') ? '#ef4444' :
                    k.includes('p75') || k.includes('p90') ? '#10b981' : '#06b6d4'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {/* Probability Bars */}
      <Panel title="Directional Probabilities">
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={[
            { label: 'Up 1W', prob: (prob.prob_up_1w || 0) * 100 },
            { label: 'Up 1M', prob: (prob.prob_up_1m || 0) * 100 },
            { label: 'Up 3M', prob: (prob.prob_up_3m || 0) * 100 },
            { label: '>Target', prob: (prob.prob_above_target || 0) * 100 },
            { label: '<Stop', prob: (prob.prob_below_stop || 0) * 100 },
          ].filter(d => d.prob > 0)} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis type="number" tick={{ fontSize: 9, fill: '#9ca3af' }} domain={[0, 100]} tickFormatter={v => `${v}%`} />
            <YAxis type="category" dataKey="label" tick={{ fontSize: 10, fill: '#9ca3af' }} width={60} />
            <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
              formatter={v => [`${v.toFixed(1)}%`, 'Probability']} />
            <ReferenceLine x={50} stroke="#6b7280" strokeDasharray="3 3" />
            <Bar dataKey="prob" radius={[0, 4, 4, 0]}>
              {[
                { label: 'Up 1W', prob: (prob.prob_up_1w || 0) * 100 },
                { label: 'Up 1M', prob: (prob.prob_up_1m || 0) * 100 },
                { label: 'Up 3M', prob: (prob.prob_up_3m || 0) * 100 },
                { label: '>Target', prob: (prob.prob_above_target || 0) * 100 },
                { label: '<Stop', prob: (prob.prob_below_stop || 0) * 100 },
              ].filter(d => d.prob > 0).map((d, i) => (
                <Cell key={i} fill={d.label === '<Stop' ? '#ef4444' : d.prob >= 50 ? '#10b981' : '#f59e0b'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Panel>
    </div>
  )
}
