import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
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
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={[
                { name: 'Personal', value: o.personal_pct || 0 },
                { name: 'Auto', value: o.auto_pct || 0 },
                { name: 'HELOC', value: o.heloc_pct || 0 },
                { name: 'Small Biz', value: o.small_biz_pct || 0 },
              ].filter(d => d.value > 0)} cx="50%" cy="50%" innerRadius={40} outerRadius={70} paddingAngle={3} dataKey="value">
                <Cell fill="#06b6d4" />
                <Cell fill="#8b5cf6" />
                <Cell fill="#10b981" />
                <Cell fill="#f59e0b" />
              </Pie>
              <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
                formatter={v => [`${v}%`]} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
            </PieChart>
          </ResponsiveContainer>
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
