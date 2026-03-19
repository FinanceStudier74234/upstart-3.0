import React from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function OriginationPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const o = analysis.origination || {}

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="Q Volume" value={o.quarterly_volume ? `$${o.quarterly_volume}M` : '--'} /></Panel>
        <Panel><Stat label="Monthly Run Rate" value={o.monthly_run_rate ? `$${o.monthly_run_rate}M` : '--'} /></Panel>
        <Panel><Stat label="QoQ Growth" value={o.qoq_growth ? `${(o.qoq_growth * 100).toFixed(0)}%` : '--'} color={o.qoq_growth > 0 ? 'text-terminal-green' : 'text-terminal-red'} /></Panel>
        <Panel><Stat label="YoY Growth" value={o.yoy_growth ? `${(o.yoy_growth * 100).toFixed(0)}%` : '--'} color={o.yoy_growth > 0 ? 'text-terminal-green' : 'text-terminal-red'} /></Panel>
        <Panel><Stat label="Accelerating" value={o.accelerating ? 'YES' : 'No'} color={o.accelerating ? 'text-terminal-green' : ''} /></Panel>
        <Panel><Stat label="Beat Guidance" value={o.beat_guidance ? 'YES' : 'No'} color={o.beat_guidance ? 'text-terminal-green' : 'text-terminal-red'} /></Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Product Mix">
          <div className="space-y-2 text-xs">
            {[['Personal', o.personal_pct], ['Auto', o.auto_pct], ['HELOC', o.heloc_pct], ['Small Biz', o.small_biz_pct]].map(([name, pct]) => (
              <div key={name} className="flex items-center gap-2">
                <span className="w-20 text-terminal-muted">{name}</span>
                <div className="flex-1 score-bar"><div className="score-fill bg-terminal-cyan" style={{width: `${pct || 0}%`}} /></div>
                <span className="w-10 text-right">{pct || 0}%</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Partners & Quality">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Bank Partners:</span> {o.bank_partner_count}</div>
            <div><span className="text-terminal-muted">Auto Dealers:</span> {o.auto_dealer_count?.toLocaleString()}</div>
            <div><span className="text-terminal-muted">New This Q:</span> {o.new_partners_quarter}</div>
            <div><span className="text-terminal-muted">Growth Trend:</span> <span className={o.partner_growth_trend === 'growing' ? 'text-terminal-green' : ''}>{o.partner_growth_trend}</span></div>
            <div><span className="text-terminal-muted">Conversion:</span> {o.conversion_rate ? `${(o.conversion_rate * 100).toFixed(0)}%` : '--'}</div>
            <div><span className="text-terminal-muted">Approval:</span> {o.approval_rate ? `${(o.approval_rate * 100).toFixed(0)}%` : '--'}</div>
            <div><span className="text-terminal-muted">Avg Loan Size:</span> ${o.avg_loan_size?.toLocaleString()}</div>
            <div><span className="text-terminal-muted">Avg Coupon:</span> {o.weighted_avg_coupon ? `${(o.weighted_avg_coupon * 100).toFixed(1)}%` : '--'}</div>
          </div>
        </Panel>
      </div>

      <ScoreBar label="Origination Momentum" value={o.origination_momentum_score} />
    </div>
  )
}
