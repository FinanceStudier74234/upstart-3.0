import React from 'react'

function scoreColor(value) {
  if (value >= 70) return 'bg-terminal-green'
  if (value >= 55) return 'bg-emerald-600'
  if (value >= 45) return 'bg-terminal-amber'
  if (value >= 30) return 'bg-orange-500'
  return 'bg-terminal-red'
}

export default function ScoreBar({ label, value, inverted = false }) {
  const display = value != null ? Math.round(value) : '--'
  const color = inverted ? scoreColor(100 - (value || 50)) : scoreColor(value || 50)
  return (
    <div className="flex items-center gap-2 text-xs" role="meter" aria-valuenow={value ?? 0} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <span className="w-36 text-terminal-muted truncate">{label}</span>
      <div className="flex-1 score-bar">
        <div className={`score-fill ${color}`} style={{ width: `${value || 0}%` }} />
      </div>
      <span className="w-8 text-right font-bold">{display}</span>
    </div>
  )
}
