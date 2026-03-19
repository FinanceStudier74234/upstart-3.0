import React from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function ShortPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const s = analysis.short || {}

  return (
    <div className="space-y-4">
      {s.do_not_short_flag && (
        <div className="bg-red-900/50 border border-terminal-red p-3 rounded text-center">
          <div className="text-terminal-red font-black text-lg">DO NOT SHORT</div>
          <div className="text-terminal-red text-xs">Conditions extremely unfavorable for short positions</div>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="SI % Float" value={s.short_pct_float ? `${s.short_pct_float.toFixed(1)}%` : '--'} /></Panel>
        <Panel><Stat label="Days to Cover" value={s.days_to_cover?.toFixed(1)} /></Panel>
        <Panel><Stat label="Cost to Borrow" value={s.cost_to_borrow ? `${s.cost_to_borrow.toFixed(1)}%` : '--'} /></Panel>
        <Panel><Stat label="Utilization" value={s.utilization ? `${s.utilization.toFixed(0)}%` : '--'} /></Panel>
        <Panel><Stat label="Available Shares" value={s.available_shares?.toLocaleString()} /></Panel>
        <Panel><Stat label="Crowding" value={s.crowding_score?.toFixed(0)} /></Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Squeeze Risk">
          <ScoreBar label="Squeeze Risk Score" value={s.squeeze_risk_score} inverted />
          <div className="mt-2 text-xs text-terminal-muted">
            {s.squeeze_risk_score > 70 ? 'HIGH RISK — Short covering cascade possible' :
             s.squeeze_risk_score > 50 ? 'MODERATE — Monitor closely' : 'LOW — Limited squeeze pressure'}
          </div>
        </Panel>

        <Panel title="Short Decision">
          <div className="space-y-2 text-xs">
            <div><span className="text-terminal-muted">Decision:</span> <span className="font-bold">{s.short_decision}</span></div>
            <div><span className="text-terminal-muted">Best Vehicle:</span> {s.best_bearish_vehicle}</div>
            {s.short_decision_explanation && (
              <div className="p-2 bg-terminal-bg rounded text-terminal-muted text-[10px]">{s.short_decision_explanation}</div>
            )}
          </div>
        </Panel>
      </div>

      {s.bearish_vehicle_comparison && (
        <Panel title="Bearish Vehicle Comparison">
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-terminal-muted border-b border-terminal-border">
                  <th className="text-left py-1">Vehicle</th>
                  <th className="text-right">Cost</th>
                  <th className="text-right">Max Loss</th>
                  <th className="text-right">Max Gain</th>
                  <th className="text-right">Rating</th>
                </tr>
              </thead>
              <tbody>
                {s.bearish_vehicle_comparison.map((v, i) => (
                  <tr key={i} className="border-b border-terminal-border/30">
                    <td className="py-1">{v.vehicle}</td>
                    <td className="text-right">{v.cost}</td>
                    <td className="text-right text-terminal-red">{v.max_loss}</td>
                    <td className="text-right text-terminal-green">{v.max_gain}</td>
                    <td className="text-right">{v.rating}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      <Panel title="Short Entry / Cover Zones">
        <div className="grid grid-cols-2 gap-4 text-xs">
          <div>
            <div className="text-terminal-red text-[10px] mb-1">SHORT ENTRY ZONES</div>
            {(s.short_entry_zones || analysis.technical?.short_zones || []).map((z, i) => (
              <div key={i}>${Array.isArray(z) ? `${z[0]?.toFixed(2)} — ${z[1]?.toFixed(2)}` : z}</div>
            ))}
            {!(s.short_entry_zones || analysis.technical?.short_zones || []).length && <div className="text-terminal-muted">None active</div>}
          </div>
          <div>
            <div className="text-terminal-green text-[10px] mb-1">COVER ZONES</div>
            {(s.cover_zones || analysis.technical?.cover_zones || []).map((z, i) => (
              <div key={i}>${Array.isArray(z) ? `${z[0]?.toFixed(2)} — ${z[1]?.toFixed(2)}` : z}</div>
            ))}
            {!(s.cover_zones || analysis.technical?.cover_zones || []).length && <div className="text-terminal-muted">None active</div>}
          </div>
        </div>
      </Panel>

      <ScoreBar label="Short Opportunity" value={s.short_opportunity_score} />
    </div>
  )
}
