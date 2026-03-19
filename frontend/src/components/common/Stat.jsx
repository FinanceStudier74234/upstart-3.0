import React from 'react'

export default function Stat({ label, value, color, sub }) {
  return (
    <div>
      <div className="text-terminal-muted text-[10px] uppercase">{label}</div>
      <div className={`text-lg font-bold ${color || 'text-terminal-text'}`}>{value ?? '--'}</div>
      {sub && <div className="text-[10px] text-terminal-muted">{sub}</div>}
    </div>
  )
}
