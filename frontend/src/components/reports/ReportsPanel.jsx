import React, { useState, useEffect } from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'
import { api } from '../../services/api'

export default function ReportsPanel({ analysis }) {
  const [alerts, setAlerts] = useState([])
  const dg = analysis?.data_governance || {}

  useEffect(() => {
    api.alerts().then(r => setAlerts(r.alerts || [])).catch(() => {})
  }, [analysis])

  const exportCsv = async () => {
    const blob = await api.exportCsv()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'upst_analysis.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  const exportJson = async () => {
    const blob = await api.exportJson()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'upst_analysis.json'; a.click()
    URL.revokeObjectURL(url)
  }

  const exportSummary = async () => {
    const blob = await api.exportSummary()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'upst_daily_summary.txt'; a.click()
    URL.revokeObjectURL(url)
  }

  const severityColor = (s) => s === 'urgent' || s === 'critical' ? 'text-terminal-red' : s === 'warning' ? 'text-terminal-amber' : 'text-terminal-muted'

  return (
    <div className="space-y-4">
      <Panel title="Export">
        <div className="flex gap-3">
          <button onClick={exportCsv} className="px-3 py-1.5 bg-terminal-panel border border-terminal-border rounded text-xs hover:bg-terminal-border">Export CSV</button>
          <button onClick={exportJson} className="px-3 py-1.5 bg-terminal-panel border border-terminal-border rounded text-xs hover:bg-terminal-border">Export JSON</button>
          <button onClick={exportSummary} className="px-3 py-1.5 bg-terminal-panel border border-terminal-border rounded text-xs hover:bg-terminal-border">Daily Summary (.txt)</button>
        </div>
      </Panel>

      <Panel title={`Alerts (${alerts.length})`}>
        {alerts.length > 0 ? (
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {alerts.map((a, i) => (
              <div key={i} className="p-2 bg-terminal-bg rounded flex gap-3 items-start">
                <span className={`text-[10px] font-bold uppercase ${severityColor(a.severity)}`}>{a.severity}</span>
                <div className="flex-1">
                  <div className="text-xs font-bold">{a.title}</div>
                  <div className="text-[10px] text-terminal-muted">{a.message}</div>
                </div>
                <span className="text-[10px] text-terminal-muted">{a.timestamp?.slice(11, 19)}</span>
              </div>
            ))}
          </div>
        ) : <div className="text-xs text-terminal-muted">No alerts</div>}
      </Panel>

      <Panel title="Data Quality Dashboard">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          <Stat label="Quality Score" value={dg.overall_quality_score?.toFixed(0)} />
          <Stat label="Freshness" value={dg.overall_freshness_score ? `${dg.overall_freshness_score}%` : '--'} />
          <Stat label="Coverage" value={dg.overall_coverage_pct ? `${dg.overall_coverage_pct}%` : '--'} />
          <Stat label="Snooping Risk" value={dg.data_snooping_risk?.toFixed(0)} />
        </div>

        {dg.sources && dg.sources.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-terminal-muted border-b border-terminal-border">
                  <th className="text-left py-1">Source</th>
                  <th className="text-left">Provider</th>
                  <th className="text-center">Freshness</th>
                  <th className="text-right">Quality</th>
                  <th className="text-right">Coverage</th>
                </tr>
              </thead>
              <tbody>
                {dg.sources.map((s, i) => (
                  <tr key={i} className="border-b border-terminal-border/30">
                    <td className="py-1">{s.name}</td>
                    <td>{s.source}</td>
                    <td className={`text-center ${s.freshness === 'live' ? 'text-terminal-green' : s.freshness === 'stale' ? 'text-terminal-amber' : 'text-terminal-red'}`}>{s.freshness}</td>
                    <td className="text-right">{s.quality_score}</td>
                    <td className="text-right">{s.coverage_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {dg.recommendations && dg.recommendations.length > 0 && (
        <Panel title="Recommendations">
          <ul className="space-y-1 text-xs">
            {dg.recommendations.map((r, i) => <li key={i} className="text-terminal-amber">- {r}</li>)}
          </ul>
        </Panel>
      )}

      {dg.missing_data_points && dg.missing_data_points.length > 0 && (
        <Panel title="Coverage Gaps">
          <ul className="space-y-1 text-xs">
            {dg.missing_data_points.map((g, i) => <li key={i} className="text-terminal-red">- {g}</li>)}
          </ul>
        </Panel>
      )}

      <ScoreBar label="Data Governance Score" value={dg.data_governance_score} />
    </div>
  )
}
