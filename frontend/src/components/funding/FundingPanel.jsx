import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  Cell,
} from 'recharts'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function FundingPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const f = analysis.funding || {}

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="Total Committed" value={f.total_committed ? `$${f.total_committed}B` : '--'} /></Panel>
        <Panel><Stat label="Total Drawn" value={f.total_drawn ? `$${f.total_drawn}B` : '--'} /></Panel>
        <Panel><Stat label="Available" value={f.available_capacity ? `$${f.available_capacity}B` : '--'} color="text-terminal-green" /></Panel>
        <Panel><Stat label="Utilization" value={f.utilization_pct ? `${f.utilization_pct}%` : '--'} /></Panel>
        <Panel><Stat label="Coverage" value={f.months_coverage ? `${f.months_coverage} mo` : '--'} /></Panel>
        <Panel><Stat label="Partners" value={f.partner_count} /></Panel>
      </div>

      <Panel title="Warehouse Facilities">
        <div className="overflow-x-auto">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-terminal-muted border-b border-terminal-border">
                <th className="text-left py-1">Facility</th>
                <th className="text-left">Partner</th>
                <th className="text-right">Committed ($M)</th>
                <th className="text-right">Drawn ($M)</th>
                <th className="text-right">Maturity</th>
                <th className="text-right">Mo. Left</th>
                <th className="text-right">Renewal</th>
                <th className="text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {(f.facilities || []).map((fac, i) => (
                <tr key={i} className="border-b border-terminal-border/30">
                  <td className="py-1 font-bold">{fac.name}</td>
                  <td>{fac.partner}</td>
                  <td className="text-right">${fac.committed_amount}</td>
                  <td className="text-right">${fac.drawn_amount}</td>
                  <td className="text-right">{fac.maturity_date}</td>
                  <td className={`text-right ${fac.months_to_maturity <= 6 ? 'text-terminal-red' : ''}`}>{fac.months_to_maturity}</td>
                  <td className="text-right">{(fac.renewal_probability * 100).toFixed(0)}%</td>
                  <td className={`text-center ${fac.status === 'maturing' ? 'text-terminal-amber' : fac.status === 'at_risk' ? 'text-terminal-red' : 'text-terminal-green'}`}>{fac.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {/* Facility Maturity Waterfall */}
      {(f.facilities || []).length > 0 && (
        <Panel title="Facility Maturity Waterfall">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={(f.facilities || []).map(fac => ({
              name: fac.name?.slice(0, 12) || 'Unknown',
              months: fac.months_to_maturity || 0,
              committed: fac.committed_amount || 0,
            }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="name" tick={{ fontSize: 8, fill: '#9ca3af' }} angle={-15} />
              <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} label={{ value: 'Months', angle: -90, position: 'insideLeft', fontSize: 9, fill: '#9ca3af' }} />
              <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
                formatter={(v, name) => [name === 'months' ? `${v} months` : `$${v}M`, name === 'months' ? 'To Maturity' : 'Committed']} />
              <Bar dataKey="months" name="months" radius={[4, 4, 0, 0]}>
                {(f.facilities || []).map((fac, i) => (
                  <Cell key={i} fill={fac.months_to_maturity <= 6 ? '#ef4444' : fac.months_to_maturity <= 12 ? '#f59e0b' : '#10b981'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Concentration Risk">
          <div className="space-y-1 text-xs">
            <div><span className="text-terminal-muted">HHI:</span> {f.hhi_concentration?.toFixed(0)} {f.hhi_concentration > 3000 ? '(Concentrated)' : '(Diversified)'}</div>
            <div><span className="text-terminal-muted">Top Partner:</span> {f.top_partner_pct?.toFixed(1)}% of capacity</div>
            <div><span className="text-terminal-muted">Maturity Wall:</span> <span className={f.maturity_wall_risk ? 'text-terminal-red' : 'text-terminal-green'}>{f.maturity_wall_risk ? 'YES — Risk' : 'No'}</span></div>
            <div><span className="text-terminal-muted">Maturing in 6mo:</span> {f.facilities_maturing_6mo} facilities</div>
          </div>
        </Panel>

        <Panel title="Quality Metrics">
          <div className="space-y-1 text-xs">
            <div><span className="text-terminal-muted">Avg Renewal Prob:</span> {(f.avg_renewal_prob * 100)?.toFixed(0)}%</div>
            <div><span className="text-terminal-muted">Covenant Issues:</span> <span className={f.has_covenant_issues ? 'text-terminal-red' : 'text-terminal-green'}>{f.has_covenant_issues ? 'YES' : 'None'}</span></div>
            <div><span className="text-terminal-muted">Active Waivers:</span> {f.waivers_active}</div>
            <div><span className="text-terminal-muted">Avg Mo. to Maturity:</span> {f.avg_months_to_maturity?.toFixed(1)}</div>
          </div>
        </Panel>
      </div>

      <ScoreBar label="Funding Strength" value={f.funding_strength_score} />
    </div>
  )
}
