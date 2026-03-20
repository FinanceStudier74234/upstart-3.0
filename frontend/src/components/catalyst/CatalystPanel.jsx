import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  Cell,
} from 'recharts'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function CatalystPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const c = analysis.catalyst || {}

  const impactColor = (i) => i === 'bullish' ? 'text-terminal-green' : i === 'bearish' ? 'text-terminal-red' : 'text-terminal-amber'
  const magColor = (m) => m === 'extreme' ? 'text-terminal-red' : m === 'high' ? 'text-terminal-amber' : ''

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Panel><Stat label="Next Earnings" value={c.next_earnings_date || '--'} /></Panel>
        <Panel><Stat label="Days to Earnings" value={c.days_to_earnings} color={c.days_to_earnings <= 14 ? 'text-terminal-amber' : ''} /></Panel>
        <Panel><Stat label="Expected Move" value={c.earnings_expected_move ? `${c.earnings_expected_move}%` : '--'} /></Panel>
        <Panel><Stat label="Beat Streak" value={c.earnings_beat_streak} color="text-terminal-green" /></Panel>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Panel><Stat label="Catalysts (30d)" value={c.catalysts_next_30d} /></Panel>
        <Panel><Stat label="Net Sentiment" value={c.net_catalyst_sentiment?.toFixed(0)} color={c.net_catalyst_sentiment > 0 ? 'text-terminal-green' : 'text-terminal-red'} /></Panel>
        <Panel><Stat label="Dominant Type" value={c.dominant_catalyst_type} /></Panel>
        <Panel><Stat label="Binary Risk" value={c.binary_event_risk?.toFixed(0)} color={c.binary_event_risk > 60 ? 'text-terminal-red' : ''} /></Panel>
      </div>

      {/* Catalyst Timeline Chart */}
      {c.upcoming && c.upcoming.length > 0 && (
        <Panel title="Catalyst Impact Timeline">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={c.upcoming.slice(0, 10).map(evt => ({
              name: (evt.name || '').slice(0, 15),
              impact: evt.expected_impact === 'bullish' ? 1 : evt.expected_impact === 'bearish' ? -1 : 0,
              magnitude: evt.magnitude === 'extreme' ? 3 : evt.magnitude === 'high' ? 2 : 1,
            }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="name" tick={{ fontSize: 8, fill: '#9ca3af' }} angle={-15} />
              <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} domain={[-3, 3]} />
              <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
                formatter={(v, name) => [Math.abs(v), name === 'impact' ? 'Direction' : 'Magnitude']} />
              <Bar dataKey="magnitude" name="Magnitude">
                {c.upcoming.slice(0, 10).map((evt, i) => (
                  <Cell key={i} fill={evt.expected_impact === 'bullish' ? '#10b981' :
                    evt.expected_impact === 'bearish' ? '#ef4444' : '#f59e0b'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      <Panel title="Upcoming Catalysts">
        {c.upcoming && c.upcoming.length > 0 ? (
          <div className="space-y-2">
            {c.upcoming.map((evt, i) => (
              <div key={i} className="p-2 bg-terminal-bg rounded flex gap-3 items-start text-xs">
                <div className="w-20 text-terminal-muted">{evt.date}</div>
                <div className="flex-1">
                  <div className="font-bold">{evt.name}</div>
                  <div className="text-[10px] text-terminal-muted">{evt.description}</div>
                </div>
                <span className={`text-[10px] ${impactColor(evt.expected_impact)}`}>{evt.expected_impact}</span>
                <span className={`text-[10px] ${magColor(evt.magnitude)}`}>{evt.magnitude}</span>
              </div>
            ))}
          </div>
        ) : <div className="text-xs text-terminal-muted">No upcoming catalysts</div>}
      </Panel>

      {c.recent && c.recent.length > 0 && (
        <Panel title="Recent Catalysts">
          <div className="space-y-2">
            {c.recent.map((evt, i) => (
              <div key={i} className="p-2 bg-terminal-bg rounded flex gap-3 items-start text-xs">
                <div className="w-20 text-terminal-muted">{evt.date}</div>
                <div className="flex-1">
                  <div className="font-bold">{evt.name}</div>
                  <div className="text-[10px] text-terminal-muted">{evt.description}</div>
                </div>
                <span className={`text-[10px] ${impactColor(evt.expected_impact)}`}>{evt.expected_impact}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <ScoreBar label="Catalyst Density" value={c.catalyst_density_score} />
    </div>
  )
}
