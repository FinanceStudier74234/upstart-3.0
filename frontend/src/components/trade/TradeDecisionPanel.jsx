import React from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function TradeDecisionPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
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
          <div className="grid grid-cols-5 gap-2 text-xs text-center">
            {Object.entries(prob.cone_1m).map(([k, v]) => (
              <div key={k}>
                <div className="text-terminal-muted text-[10px]">{k.toUpperCase()}</div>
                <div className="font-bold">${v?.toFixed(2)}</div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  )
}
