import React from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function ForecastPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const fc = analysis.forecast || {}
  const prob = analysis.probability || {}

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Panel><Stat label="Ensemble Point" value={fc.ensemble_point ? `$${fc.ensemble_point}` : '--'} color="text-terminal-cyan" /></Panel>
        <Panel><Stat label="Lower (80%)" value={fc.ensemble_lower ? `$${fc.ensemble_lower}` : '--'} color="text-terminal-red" /></Panel>
        <Panel><Stat label="Upper (80%)" value={fc.ensemble_upper ? `$${fc.ensemble_upper}` : '--'} color="text-terminal-green" /></Panel>
        <Panel><Stat label="Model Agreement" value={fc.model_agreement ? `${(fc.model_agreement * 100).toFixed(0)}%` : '--'} /></Panel>
        <Panel><Stat label="Confidence" value={fc.confidence_score?.toFixed(0)} /></Panel>
      </div>

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

      <Panel title="Regime Probabilities">
        <div className="grid grid-cols-3 gap-4 text-center text-xs">
          <div>
            <div className="text-terminal-green text-[10px]">BULL</div>
            <div className="text-lg font-bold">{prob.prob_bull_regime ? `${(prob.prob_bull_regime * 100).toFixed(0)}%` : '--'}</div>
          </div>
          <div>
            <div className="text-terminal-muted text-[10px]">NEUTRAL</div>
            <div className="text-lg font-bold">{prob.prob_neutral_regime ? `${(prob.prob_neutral_regime * 100).toFixed(0)}%` : '--'}</div>
          </div>
          <div>
            <div className="text-terminal-red text-[10px]">BEAR</div>
            <div className="text-lg font-bold">{prob.prob_bear_regime ? `${(prob.prob_bear_regime * 100).toFixed(0)}%` : '--'}</div>
          </div>
        </div>
      </Panel>
    </div>
  )
}
