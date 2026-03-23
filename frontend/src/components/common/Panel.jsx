import React from 'react'

export default function Panel({ title, children, className = '' }) {
  return (
    <section className={`panel ${className}`} aria-label={title || undefined}>
      {title && <h2 className="text-xs uppercase tracking-wider text-terminal-cyan mb-3 font-bold">{title}</h2>}
      {children}
    </section>
  )
}
