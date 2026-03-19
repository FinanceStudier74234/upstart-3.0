import React from 'react'

export default function Panel({ title, children, className = '' }) {
  return (
    <div className={`panel ${className}`}>
      {title && <h3 className="text-xs uppercase tracking-wider text-terminal-cyan mb-3 font-bold">{title}</h3>}
      {children}
    </div>
  )
}
