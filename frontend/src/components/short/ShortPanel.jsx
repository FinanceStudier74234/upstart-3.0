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
          <div className="text-terminal-red text-xs mt-1">
            {s.do_not_short_reasons?.join(' | ') || 'Conditions extremely unfavorable for short positions'}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="SI % Float" value={s.short_pct_float ? `${s.short_pct_float.toFixed(1)}%` : '--'} /></Panel>
        <Panel><Stat label="Days to Cover" value={s.days_to_cover?.toFixed(1)} /></Panel>
        <Panel><Stat label="Cost to Borrow" value={s.cost_to_borrow ? `${s.cost_to_borrow.toFixed(1)}%` : '--'} /></Panel>
        <Panel><Stat label="Utilization" value={s.utilization ? `${s.utilization.toFixed(0)}%` : '--'} /></Panel>
        <Panel><Stat label="Available Shares" value={s.shares_available?.toLocaleString()} /></Panel>
        <Panel><Stat label="Crowding" value={s.crowding_score?.toFixed(0)} /></Panel>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Panel><Stat label="SI Change" value={s.short_change_pct != null ? `${s.short_change_pct.toFixed(1)}%` : '--'}
          color={s.short_change_pct > 0 ? 'text-terminal-red' : 'text-terminal-green'} /></Panel>
        <Panel><Stat label="SI Trend" value={s.short_interest_trend || '--'} /></Panel>
        <Panel><Stat label="Crowding Change" value={s.crowding_change || '--'} /></Panel>
        <Panel><Stat label="Borrow Trend" value={s.borrow_fee_trend || '--'} /></Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Squeeze Risk">
          <ScoreBar label="Squeeze Risk Score" value={s.squeeze_risk_score} inverted />
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Gamma Squeeze:</span> {s.gamma_squeeze_risk?.toFixed(1) || '--'}</div>
            <div><span className="text-terminal-muted">Forced Cover P:</span> {s.forced_cover_probability ? `${(s.forced_cover_probability * 100).toFixed(0)}%` : '--'}</div>
          </div>
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

      {/* Setup Detection */}
      <Panel title="Setup Detection">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <div className={`p-2 rounded ${s.failed_rally_setup ? 'bg-red-900/30 border border-terminal-red' : 'bg-terminal-bg'}`}>
            <div className="text-terminal-muted text-[10px]">Failed Rally</div>
            <div className={`font-bold ${s.failed_rally_setup ? 'text-terminal-red' : 'text-terminal-muted'}`}>
              {s.failed_rally_setup ? 'ACTIVE' : 'Inactive'}
            </div>
          </div>
          <div className={`p-2 rounded ${s.breakdown_setup ? 'bg-red-900/30 border border-terminal-red' : 'bg-terminal-bg'}`}>
            <div className="text-terminal-muted text-[10px]">Breakdown</div>
            <div className={`font-bold ${s.breakdown_setup ? 'text-terminal-red' : 'text-terminal-muted'}`}>
              {s.breakdown_setup ? 'ACTIVE' : 'Inactive'}
            </div>
          </div>
          <div className={`p-2 rounded ${s.lower_high_confirmed ? 'bg-red-900/30 border border-terminal-red' : 'bg-terminal-bg'}`}>
            <div className="text-terminal-muted text-[10px]">Lower High</div>
            <div className={`font-bold ${s.lower_high_confirmed ? 'text-terminal-red' : 'text-terminal-muted'}`}>
              {s.lower_high_confirmed ? 'CONFIRMED' : 'Not Confirmed'}
            </div>
          </div>
          <div className={`p-2 rounded ${s.momentum_breakdown ? 'bg-red-900/30 border border-terminal-red' : 'bg-terminal-bg'}`}>
            <div className="text-terminal-muted text-[10px]">Momentum BD</div>
            <div className={`font-bold ${s.momentum_breakdown ? 'text-terminal-red' : 'text-terminal-muted'}`}>
              {s.momentum_breakdown ? 'ACTIVE' : 'Inactive'}
            </div>
          </div>
        </div>
      </Panel>

      {/* Thesis Factors */}
      {s.thesis_factors && s.thesis_factors.length > 0 && (
        <Panel title="Short Thesis Factors">
          <div className="space-y-1">
            {s.thesis_factors.map((f, i) => (
              <div key={i} className="flex items-center gap-3 text-xs">
                <span className={`w-2 h-2 rounded-full ${f.direction === 'bearish' ? 'bg-terminal-red' : f.direction === 'caution' ? 'bg-terminal-amber' : 'bg-terminal-green'}`} />
                <span className="text-terminal-text">{f.factor?.replace(/_/g, ' ')}</span>
                <span className="text-terminal-muted text-[10px]">strength: {f.strength?.toFixed(1)}</span>
                <span className={`text-[10px] font-bold ${f.direction === 'bearish' ? 'text-terminal-red' : f.direction === 'caution' ? 'text-terminal-amber' : 'text-terminal-green'}`}>
                  {f.direction?.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Downside Targets */}
      {s.downside_targets && s.downside_targets.length > 0 && (
        <Panel title="Downside Targets">
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-terminal-muted border-b border-terminal-border">
                  <th className="text-left py-1">Level</th>
                  <th className="text-right">Price</th>
                  <th className="text-right">Move %</th>
                  <th className="text-right">Probability</th>
                  <th className="text-right">Timeframe</th>
                </tr>
              </thead>
              <tbody>
                {s.downside_targets.map((t, i) => (
                  <tr key={i} className="border-b border-terminal-border/30">
                    <td className="py-1">{t.label}</td>
                    <td className="text-right text-terminal-red">${t.level?.toFixed(2)}</td>
                    <td className="text-right">{t.pct_move?.toFixed(1)}%</td>
                    <td className="text-right">{(t.probability * 100)?.toFixed(0)}%</td>
                    <td className="text-right text-terminal-muted">{t.timeframe}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {/* Bearish Vehicle Comparison */}
      {s.bearish_comparison && typeof s.bearish_comparison === 'object' && (
        <Panel title="Bearish Vehicle Comparison">
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-terminal-muted border-b border-terminal-border">
                  <th className="text-left py-1">Vehicle</th>
                  <th className="text-right">Max Risk</th>
                  <th className="text-right">Squeeze Exp.</th>
                  <th className="text-right">Feasibility</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(s.bearish_comparison)
                  .filter(([k]) => k !== 'best')
                  .map(([k, v]) => (
                  <tr key={k} className={`border-b border-terminal-border/30 ${k === s.best_bearish_vehicle ? 'bg-terminal-cyan/10' : ''}`}>
                    <td className="py-1 font-bold">{v.vehicle?.replace(/_/g, ' ')}{k === s.best_bearish_vehicle ? ' ★' : ''}</td>
                    <td className="text-right text-terminal-red">{v.max_risk}</td>
                    <td className="text-right">{v.squeeze_exposure}</td>
                    <td className="text-right">{v.feasibility}</td>
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
            {(s.short_entry_zones || []).map((z, i) => (
              <div key={i}>${Array.isArray(z) ? `${z[0]?.toFixed(2)} — ${z[1]?.toFixed(2)}` : z}</div>
            ))}
            {!(s.short_entry_zones || []).length && <div className="text-terminal-muted">None active</div>}
          </div>
          <div>
            <div className="text-terminal-green text-[10px] mb-1">COVER ZONES</div>
            {(s.cover_zones || []).map((z, i) => (
              <div key={i}>${Array.isArray(z) ? `${z[0]?.toFixed(2)} — ${z[1]?.toFixed(2)}` : z}</div>
            ))}
            {!(s.cover_zones || []).length && <div className="text-terminal-muted">None active</div>}
          </div>
        </div>
        {s.short_invalidation_level && (
          <div className="mt-2 text-xs text-terminal-amber">
            Invalidation Level: ${s.short_invalidation_level.toFixed(2)}
          </div>
        )}
      </Panel>

      {/* Timeframe Analysis */}
      {s.timeframe_analysis && Object.keys(s.timeframe_analysis).length > 0 && (
        <Panel title="Timeframe Analysis">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(s.timeframe_analysis).map(([tf, data]) => (
              <div key={tf} className="p-2 bg-terminal-bg rounded text-xs">
                <div className="text-terminal-muted text-[10px] mb-1">{tf.toUpperCase()}</div>
                <div><span className="text-terminal-muted">Bearish:</span> {data.bearish ? 'YES' : 'NO'}</div>
                <div><span className="text-terminal-muted">Shortable:</span>
                  <span className={data.shortable ? 'text-terminal-green' : 'text-terminal-red'}>
                    {' '}{data.shortable ? 'YES' : 'NO'}
                  </span>
                </div>
                <div><span className="text-terminal-muted">Squeeze:</span> {data.squeeze_risk?.toFixed(0)}</div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <ScoreBar label="Short Opportunity" value={s.short_opportunity_score} />
        <ScoreBar label="Positioning Crowdedness" value={s.positioning_crowdedness_score} inverted />
        <ScoreBar label="Bearish Structure" value={s.bearish_structure_score} />
        <ScoreBar label="Direct Short Feasibility" value={s.direct_short_feasibility_score} />
      </div>
    </div>
  )
}
