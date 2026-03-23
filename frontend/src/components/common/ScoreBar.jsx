import React, { useState } from 'react'

function scoreColor(value) {
  if (value >= 70) return 'bg-terminal-green'
  if (value >= 55) return 'bg-emerald-600'
  if (value >= 45) return 'bg-terminal-amber'
  if (value >= 30) return 'bg-orange-500'
  return 'bg-terminal-red'
}

function scoreTextColor(value) {
  if (value >= 70) return 'text-terminal-green'
  if (value >= 55) return 'text-emerald-400'
  if (value >= 45) return 'text-terminal-amber'
  if (value >= 30) return 'text-orange-400'
  return 'text-terminal-red'
}

export default function ScoreBar({ label, value, inverted = false, components, confidence }) {
  const [expanded, setExpanded] = useState(false)
  const display = value != null ? Math.round(value) : '--'
  const effectiveValue = inverted ? 100 - (value || 50) : (value || 50)
  const color = scoreColor(effectiveValue)
  const textColor = scoreTextColor(effectiveValue)
  const hasDetails = components && Object.keys(components).length > 0

  return (
    <div className="text-xs">
      <div
        className={`flex items-center gap-2 ${hasDetails ? 'cursor-pointer hover:bg-terminal-border/10 rounded px-1 -mx-1' : ''}`}
        role="meter"
        aria-valuenow={value ?? 0}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        onClick={hasDetails ? () => setExpanded(!expanded) : undefined}
      >
        <span className="w-36 text-terminal-muted truncate flex items-center gap-1">
          {hasDetails && <span className="text-[8px] text-terminal-muted">{expanded ? '▼' : '▶'}</span>}
          {label}
        </span>
        <div className="flex-1 score-bar relative">
          <div className={`score-fill ${color} transition-all duration-500`} style={{ width: `${value || 0}%` }} />
          {/* 50-mark indicator */}
          <div className="absolute top-0 bottom-0 left-1/2 w-px bg-terminal-muted/30" />
        </div>
        <span className={`w-8 text-right font-bold ${textColor}`}>{display}</span>
        {confidence != null && confidence < 0.5 && (
          <span className="text-[8px] text-terminal-amber" title="Low confidence data">⚠</span>
        )}
      </div>
      {expanded && hasDetails && (
        <div className="ml-[152px] mt-1 mb-2 space-y-0.5">
          {Object.entries(components).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 text-[10px]">
              <span className="w-28 text-terminal-muted/70 truncate">{k.replace(/_/g, ' ')}</span>
              <div className="flex-1 h-1 bg-terminal-border/20 rounded overflow-hidden">
                <div
                  className={`h-full rounded ${scoreColor(typeof v === 'number' ? v : 50)}`}
                  style={{ width: `${Math.min(100, Math.max(0, typeof v === 'number' ? v : 0))}%` }}
                />
              </div>
              <span className="w-6 text-right text-terminal-muted/70">
                {typeof v === 'number' ? Math.round(v) : v}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
