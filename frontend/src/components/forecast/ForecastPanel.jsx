import React from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
         ComposedChart, Line, Area, ReferenceLine } from 'recharts'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function ForecastPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const fc = analysis.forecast || {}
  const prob = analysis.probability || {}

  // Build model comparison chart data
  const modelChartData = fc.models?.map(m => ({
    name: m.name?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || m.name,
    point: m.point,
    lower: m.lower,
    upper: m.upper,
    range: (m.upper || 0) - (m.lower || 0),
  })) || []

  // Build probability cone chart data
  const coneData = []
  if (prob.cone_1m && typeof prob.cone_1m === 'object') {
    coneData.push({ horizon: '1M', ...prob.cone_1m })
  }
  if (prob.cone_3m && typeof prob.cone_3m === 'object') {
    coneData.push({ horizon: '3M', ...prob.cone_3m })
  }

  // Regime probabilities bar data
  const regimeData = [
    { regime: 'Bull', prob: (prob.prob_bull_regime || 0) * 100, fill: '#10b981' },
    { regime: 'Neutral', prob: (prob.prob_neutral_regime || 0) * 100, fill: '#6b7280' },
    { regime: 'Bear', prob: (prob.prob_bear_regime || 0) * 100, fill: '#ef4444' },
  ]

  const currentPrice = analysis.price || 0

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Panel><Stat label="Ensemble Point" value={fc.ensemble_point ? `$${fc.ensemble_point.toFixed(2)}` : '--'} color="text-terminal-cyan" /></Panel>
        <Panel><Stat label="Lower (80%)" value={fc.ensemble_lower ? `$${fc.ensemble_lower.toFixed(2)}` : '--'} color="text-terminal-red" /></Panel>
        <Panel><Stat label="Upper (80%)" value={fc.ensemble_upper ? `$${fc.ensemble_upper.toFixed(2)}` : '--'} color="text-terminal-green" /></Panel>
        <Panel><Stat label="Model Agreement" value={fc.model_agreement ? `${(fc.model_agreement * 100).toFixed(0)}%` : '--'} /></Panel>
        <Panel><Stat label="Confidence" value={fc.confidence_score?.toFixed(0)} /></Panel>
      </div>

      {/* Model Forecast Comparison Chart */}
      {modelChartData.length > 0 && (
        <Panel title="Model Forecast Comparison">
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={modelChartData} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
              <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 10 }} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} domain={['auto', 'auto']}
                tickFormatter={(v) => `$${v.toFixed(0)}`} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #1f2937', fontSize: 11 }}
                formatter={(v) => `$${Number(v).toFixed(2)}`} />
              {currentPrice > 0 && (
                <ReferenceLine y={currentPrice} stroke="#06b6d4" strokeDasharray="3 3"
                  label={{ value: `Current $${currentPrice.toFixed(2)}`, fill: '#06b6d4', fontSize: 10 }} />
              )}
              <Bar dataKey="lower" fill="#ef444480" name="Lower" />
              <Bar dataKey="point" fill="#06b6d4" name="Point Est." />
              <Bar dataKey="upper" fill="#10b98180" name="Upper" />
            </ComposedChart>
          </ResponsiveContainer>
        </Panel>
      )}

      <Panel title="Individual Model Forecasts">
        {fc.models && fc.models.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-terminal-muted border-b border-terminal-border">
                  <th className="text-left py-1">Model</th>
                  <th className="text-right">Point Est.</th>
                  <th className="text-right">Lower</th>
                  <th className="text-right">Upper</th>
                  <th className="text-right">Range</th>
                </tr>
              </thead>
              <tbody>
                {fc.models.map((m, i) => (
                  <tr key={i} className="border-b border-terminal-border/30">
                    <td className="py-1">{m.name}</td>
                    <td className="text-right font-bold">${m.point?.toFixed(2)}</td>
                    <td className="text-right text-terminal-red">${m.lower?.toFixed(2)}</td>
                    <td className="text-right text-terminal-green">${m.upper?.toFixed(2)}</td>
                    <td className="text-right text-terminal-muted">${(m.upper - m.lower)?.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="text-xs text-terminal-muted">No forecast models available</div>}
      </Panel>

      {prob.cone_3m && Object.keys(prob.cone_3m).length > 0 && (
        <Panel title="3-Month Probability Cones">
          <div className="grid grid-cols-5 gap-3 text-center">
            {Object.entries(prob.cone_3m).map(([k, v]) => (
              <div key={k}>
                <div className="text-terminal-muted text-[10px]">{k.toUpperCase()}</div>
                <div className="font-bold text-sm">${v?.toFixed(2)}</div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Regime Probability Chart */}
      <Panel title="Regime Probabilities">
        <div className="flex items-center gap-6">
          <ResponsiveContainer width="60%" height={120}>
            <BarChart data={regimeData} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <XAxis type="number" domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 10 }}
                tickFormatter={(v) => `${v}%`} />
              <YAxis type="category" dataKey="regime" tick={{ fill: '#e5e7eb', fontSize: 11 }} width={60} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', fontSize: 11 }}
                formatter={(v) => `${v.toFixed(1)}%`} />
              <Bar dataKey="prob" name="Probability">
                {regimeData.map((entry, idx) => (
                  <Cell key={idx} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-1 gap-2 text-xs">
            {regimeData.map(r => (
              <div key={r.regime} className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ background: r.fill }} />
                <span className="text-terminal-text">{r.regime}: {r.prob.toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      </Panel>
    </div>
  )
}
