import React from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function RiskPanel({ analysis }) {
  if (!analysis) return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="panel p-3 animate-pulse">
            <div className="h-3 bg-terminal-border/30 rounded w-20 mb-2" />
            <div className="h-6 bg-terminal-border/30 rounded w-16" />
          </div>
        ))}
      </div>
    </div>
  )
  const r = analysis?.risk || {}
  const s = analysis?.stress || {}

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="VaR 95% (1d)" value={r.var_95_1d ? `$${r.var_95_1d.toFixed(2)}` : '--'} /></Panel>
        <Panel><Stat label="VaR 99% (1d)" value={r.var_99_1d ? `$${r.var_99_1d.toFixed(2)}` : '--'} /></Panel>
        <Panel><Stat label="CVaR 95%" value={r.cvar_95_1d ? `$${r.cvar_95_1d.toFixed(2)}` : '--'} /></Panel>
        <Panel><Stat label="VaR 95% (1m)" value={r.var_95_1m ? `$${r.var_95_1m.toFixed(2)}` : '--'} /></Panel>
        <Panel><Stat label="Max DD" value={r.max_drawdown ? `${r.max_drawdown.toFixed(1)}%` : '--'} color="text-terminal-red" /></Panel>
        <Panel><Stat label="Current DD" value={r.current_drawdown ? `${r.current_drawdown.toFixed(1)}%` : '--'} /></Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Position Sizing Recommendations">
          {(() => {
            const sizingData = [
              { method: 'Vol-Target', pct: r.vol_target_size_pct || 0, fill: '#3b82f6' },
              { method: 'Full Kelly', pct: r.kelly_size_pct || 0, fill: '#8b5cf6' },
              { method: '1/4 Kelly', pct: r.quarter_kelly_pct || 0, fill: '#06b6d4' },
              { method: 'Max-Loss', pct: r.max_loss_size_pct || 0, fill: '#f59e0b' },
              { method: 'Recommended', pct: r.recommended_size_pct || 0, fill: '#10b981' },
            ]
            return (
              <>
                <ResponsiveContainer width="100%" height={140}>
                  <BarChart data={sizingData} layout="vertical" margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
                    <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }}
                      tickFormatter={(v) => `${v.toFixed(1)}%`} />
                    <YAxis type="category" dataKey="method" tick={{ fill: '#e5e7eb', fontSize: 10 }} width={80} />
                    <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', fontSize: 11 }}
                      formatter={(v) => `${Number(v).toFixed(2)}%`} />
                    <Bar dataKey="pct" name="Size %">
                      {sizingData.map((entry, idx) => (
                        <Cell key={idx} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-2 p-2 bg-terminal-bg rounded text-xs">
                  <span className="text-terminal-muted">Recommended: </span>
                  <span className="text-terminal-cyan font-bold">{r.recommended_size_pct?.toFixed(1)}% of portfolio</span>
                </div>
              </>
            )
          })()}
        </Panel>

        <Panel title="Tail Risk & Distribution">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Skewness:</span> {r.skewness?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Kurtosis:</span> {r.kurtosis?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Tail Ratio:</span> {r.tail_ratio?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Avg DD:</span> {r.avg_drawdown?.toFixed(1)}%</div>
            <div><span className="text-terminal-muted">Risk of Ruin:</span>
              <span className={r.risk_of_ruin_pct > 10 ? 'text-terminal-red font-bold' : ''}> {r.risk_of_ruin_pct?.toFixed(2)}%</span>
            </div>
            <div><span className="text-terminal-muted">Survival:</span> {r.survival_probability?.toFixed(1)}%</div>
          </div>
        </Panel>
      </div>

      <Panel title="Balance Sheet Stress Test">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          <Stat label="Cash" value={s.cash_and_equivalents ? `$${s.cash_and_equivalents}M` : '--'} />
          <Stat label="Net Cash" value={s.net_cash ? `$${s.net_cash}M` : '--'} color={s.net_cash > 0 ? 'text-terminal-green' : 'text-terminal-red'} />
          <Stat label="Runway" value={s.runway_months ? `${s.runway_months} mo` : '--'} />
          <Stat label="P(Distress)" value={s.probability_of_distress ? `${s.probability_of_distress}%` : '--'} color={s.probability_of_distress > 20 ? 'text-terminal-red' : ''} />
        </div>

        {s.scenarios && s.scenarios.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-terminal-muted border-b border-terminal-border">
                  <th className="text-left py-1">Scenario</th>
                  <th className="text-right">Funding</th>
                  <th className="text-right">Revenue</th>
                  <th className="text-right">Survival (mo)</th>
                  <th className="text-center">Survives?</th>
                  <th className="text-center">Severity</th>
                </tr>
              </thead>
              <tbody>
                {s.scenarios.map((sc, i) => (
                  <tr key={i} className="border-b border-terminal-border/30">
                    <td className="py-1">{sc.name}</td>
                    <td className="text-right">{sc.funding_impact_pct}%</td>
                    <td className="text-right">{sc.revenue_impact_pct}%</td>
                    <td className="text-right">{sc.cash_burn_months?.toFixed(1)}</td>
                    <td className={`text-center font-bold ${sc.survives ? 'text-terminal-green' : 'text-terminal-red'}`}>{sc.survives ? 'YES' : 'NO'}</td>
                    <td className={`text-center ${sc.severity === 'extreme' ? 'text-terminal-red' : sc.severity === 'severe' ? 'text-terminal-amber' : ''}`}>{sc.severity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-2 gap-4">
        <ScoreBar label="Liquidity Score" value={s.liquidity_score} />
        <ScoreBar label="Balance Sheet Health" value={s.balance_sheet_health_score} />
      </div>
    </div>
  )
}
