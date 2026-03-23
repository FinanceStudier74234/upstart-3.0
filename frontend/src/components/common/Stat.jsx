import React from 'react'

export default function Stat({ label, value, color, sub }) {
  return (
    <dl className="m-0">
      <dt className="text-terminal-muted text-[10px] uppercase">{label}</dt>
      <dd className={`text-lg font-bold m-0 ${color || 'text-terminal-text'}`}>{value ?? '--'}</dd>
      {sub && <dd className="text-[10px] text-terminal-muted m-0">{sub}</dd>}
    </dl>
  )
}
