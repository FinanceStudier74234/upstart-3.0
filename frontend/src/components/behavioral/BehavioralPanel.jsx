import React from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function BehavioralPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const b = analysis.behavioral || {}

  const flag = (val, label) => val ? (
    <span className="text-terminal-red text-xs font-bold">{label}</span>
  ) : (
    <span className="text-terminal-muted text-xs">--</span>
  )

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Panel><Stat label="Panic Selling" value={b.panic_selling ? 'DETECTED' : 'No'}
          color={b.panic_selling ? 'text-terminal-red' : 'text-terminal-green'} /></Panel>
        <Panel><Stat label="Euphoric Buying" value={b.euphoric_buying ? 'DETECTED' : 'No'}
          color={b.euphoric_buying ? 'text-terminal-amber' : 'text-terminal-green'} /></Panel>
        <Panel><Stat label="Sentiment Extreme" value={b.sentiment_extreme ? 'YES' : 'No'}
          color={b.sentiment_extreme ? 'text-terminal-red' : ''} /></Panel>
        <Panel><Stat label="Signal Clarity" value={b.signal_clarity_score?.toFixed(0)} /></Panel>
      </div>

      <Panel title="Trapped Traders">
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="p-2 bg-terminal-bg rounded">
            <div className="text-terminal-muted mb-1">Trapped Longs</div>
            {flag(b.trapped_longs, 'TRAPPED')}
          </div>
          <div className="p-2 bg-terminal-bg rounded">
            <div className="text-terminal-muted mb-1">Trapped Shorts</div>
            {flag(b.trapped_shorts, 'TRAPPED')}
          </div>
        </div>
      </Panel>

      <Panel title="Exhaustion & Capitulation">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <div className="p-2 bg-terminal-bg rounded">
            <div className="text-terminal-muted mb-1">Buying Exhaustion</div>
            {flag(b.buying_exhaustion, 'EXHAUSTED')}
          </div>
          <div className="p-2 bg-terminal-bg rounded">
            <div className="text-terminal-muted mb-1">Selling Exhaustion</div>
            {flag(b.selling_exhaustion, 'EXHAUSTED')}
          </div>
          <div className="p-2 bg-terminal-bg rounded">
            <div className="text-terminal-muted mb-1">Long Capitulation</div>
            {flag(b.long_capitulation, 'CAPITULATION')}
          </div>
          <div className="p-2 bg-terminal-bg rounded">
            <div className="text-terminal-muted mb-1">Short Capitulation</div>
            {flag(b.short_capitulation, 'CAPITULATION')}
          </div>
        </div>
      </Panel>

      <div className="grid grid-cols-2 gap-3">
        <Panel><Stat label="Crowd Shift" value={b.crowd_psychology_shift || 'None'} /></Panel>
        <Panel><Stat label="Noise Level" value={b.noise_level?.toFixed(2)} /></Panel>
      </div>

      {b.dominant_signals && b.dominant_signals.length > 0 && (
        <Panel title="Dominant Signals">
          <div className="flex flex-wrap gap-2">
            {b.dominant_signals.map((sig, i) => (
              <span key={i} className="text-xs px-2 py-0.5 bg-terminal-bg rounded text-terminal-cyan">{sig}</span>
            ))}
          </div>
        </Panel>
      )}

      <ScoreBar label="Signal Clarity" value={b.signal_clarity_score} />
    </div>
  )
}
