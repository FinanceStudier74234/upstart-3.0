import React from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function OptionsPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const o = analysis.options || {}

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="ATM IV" value={o.atm_iv ? `${(o.atm_iv * 100).toFixed(0)}%` : '--'} /></Panel>
        <Panel><Stat label="IV Rank" value={o.iv_rank ? `${(o.iv_rank * 100).toFixed(0)}%` : '--'} /></Panel>
        <Panel><Stat label="IV Percentile" value={o.iv_percentile ? `${(o.iv_percentile * 100).toFixed(0)}%` : '--'} /></Panel>
        <Panel><Stat label="IV Regime" value={o.iv_regime || '--'} /></Panel>
        <Panel><Stat label="P/C Vol Ratio" value={o.put_call_volume_ratio?.toFixed(2)} /></Panel>
        <Panel><Stat label="P/C OI Ratio" value={o.put_call_oi_ratio?.toFixed(2)} /></Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Expected Move">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">1-Week:</span> {o.expected_move_1w ? `$${o.expected_move_1w.toFixed(2)}` : '--'}</div>
            <div><span className="text-terminal-muted">1-Month:</span> {o.expected_move_1m ? `$${o.expected_move_1m.toFixed(2)}` : '--'}</div>
            <div><span className="text-terminal-muted">Max Pain:</span> {o.max_pain ? `$${o.max_pain.toFixed(2)}` : '--'}</div>
            <div><span className="text-terminal-muted">Skew:</span> {o.skew_25d?.toFixed(4) || '--'}</div>
          </div>
        </Panel>

        <Panel title="Options Walls">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Call Wall:</span> {o.call_wall ? `$${o.call_wall.toFixed(2)}` : '--'}</div>
            <div><span className="text-terminal-muted">Put Wall:</span> {o.put_wall ? `$${o.put_wall.toFixed(2)}` : '--'}</div>
            <div><span className="text-terminal-muted">Total Call OI:</span> {o.total_call_oi?.toLocaleString() || '--'}</div>
            <div><span className="text-terminal-muted">Total Put OI:</span> {o.total_put_oi?.toLocaleString() || '--'}</div>
          </div>
        </Panel>
      </div>

      <Panel title="Term Structure">
        <div className="text-xs text-terminal-muted">
          {o.term_structure_indicator ? (
            <div>Term structure: <span className="text-terminal-text font-bold">{o.term_structure_indicator}</span></div>
          ) : <div>No term structure data available</div>}
        </div>
      </Panel>

      {o.unusual_activity && o.unusual_activity.length > 0 && (
        <Panel title="Unusual Activity">
          <div className="space-y-1 text-[10px]">
            {o.unusual_activity.map((a, i) => (
              <div key={i} className="flex gap-4 text-terminal-muted">
                <span>{a.type}</span>
                <span>${a.strike}</span>
                <span>{a.expiry}</span>
                <span>{a.volume?.toLocaleString()} vol</span>
                <span className={a.sentiment === 'bullish' ? 'text-terminal-green' : 'text-terminal-red'}>{a.sentiment}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <ScoreBar label="Options Sentiment" value={o.options_sentiment_score} />
    </div>
  )
}
