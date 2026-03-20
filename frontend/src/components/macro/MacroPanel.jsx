import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ReferenceLine,
} from 'recharts'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function MacroPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const m = analysis.macro || {}

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="Fed Funds" value={m.fed_funds ? `${m.fed_funds}%` : '--'} /></Panel>
        <Panel><Stat label="2Y Treasury" value={m.treasury_2y ? `${m.treasury_2y}%` : '--'} /></Panel>
        <Panel><Stat label="10Y Treasury" value={m.treasury_10y ? `${m.treasury_10y}%` : '--'} /></Panel>
        <Panel><Stat label="Yield Curve" value={m.yield_curve_2_10 ? `${m.yield_curve_2_10}bp` : '--'}
          color={m.yield_curve_inverted ? 'text-terminal-red' : 'text-terminal-green'} /></Panel>
        <Panel><Stat label="VIX" value={m.vix?.toFixed(1)} color={m.vix > 25 ? 'text-terminal-red' : ''} /></Panel>
        <Panel><Stat label="HY Spread" value={m.hy_spread ? `${m.hy_spread}bp` : '--'} /></Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Regime Classifications">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Rate Regime:</span> <span className="font-bold">{m.rate_regime}</span></div>
            <div><span className="text-terminal-muted">Credit Regime:</span> <span className="font-bold">{m.credit_regime}</span></div>
            <div><span className="text-terminal-muted">Risk Regime:</span> <span className={m.risk_regime === 'risk_off' ? 'text-terminal-red font-bold' : 'font-bold'}>{m.risk_regime}</span></div>
            <div><span className="text-terminal-muted">Liquidity:</span> <span className="font-bold">{m.liquidity_regime}</span></div>
            <div><span className="text-terminal-muted">Macro Stress:</span> <span className={m.macro_stress_regime === 'crisis' ? 'text-terminal-red font-bold' : 'font-bold'}>{m.macro_stress_regime}</span></div>
            <div><span className="text-terminal-muted">UPST Impact:</span> <span className={m.upst_macro_impact === 'headwind' ? 'text-terminal-red font-bold' : m.upst_macro_impact === 'tailwind' ? 'text-terminal-green font-bold' : 'font-bold'}>{m.upst_macro_impact}</span></div>
          </div>
        </Panel>

        <Panel title="Economic Indicators">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">CPI YoY:</span> {m.cpi_yoy ? `${m.cpi_yoy}%` : '--'}</div>
            <div><span className="text-terminal-muted">PCE YoY:</span> {m.pce_yoy ? `${m.pce_yoy}%` : '--'}</div>
            <div><span className="text-terminal-muted">Unemployment:</span> {m.unemployment ? `${m.unemployment}%` : '--'}</div>
            <div><span className="text-terminal-muted">Initial Claims:</span> {m.initial_claims?.toLocaleString() || '--'}</div>
            <div><span className="text-terminal-muted">Recession Prob:</span> {m.recession_prob ? `${m.recession_prob}%` : '--'}</div>
            <div><span className="text-terminal-muted">Lending Stds:</span> {m.lending_standards || '--'}</div>
          </div>
        </Panel>
      </div>

      {/* Yield Curve Visualization */}
      <Panel title="Yield Curve">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={[
            { tenor: 'Fed Funds', yield: m.fed_funds || 0 },
            { tenor: '2Y', yield: m.treasury_2y || 0 },
            { tenor: '10Y', yield: m.treasury_10y || 0 },
          ].filter(d => d.yield > 0)}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="tenor" tick={{ fontSize: 10, fill: '#9ca3af' }} />
            <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} tickFormatter={v => `${v}%`} domain={[0, 'auto']} />
            <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
              formatter={v => [`${v.toFixed(2)}%`, 'Yield']} />
            <Bar dataKey="yield" radius={[4, 4, 0, 0]}
              fill={m.yield_curve_inverted ? '#ef4444' : '#06b6d4'} />
          </BarChart>
        </ResponsiveContainer>
        {m.yield_curve_inverted && (
          <div className="text-center text-terminal-red text-[10px] mt-1 font-bold">INVERTED — Recession Signal</div>
        )}
      </Panel>

      {/* Macro Stress Radar */}
      <Panel title="Macro Stress Radar">
        <ResponsiveContainer width="100%" height={250}>
          <RadarChart data={[
            { metric: 'VIX', value: Math.min((m.vix || 15) / 40 * 100, 100) },
            { metric: 'HY Spread', value: Math.min((m.hy_spread || 300) / 800 * 100, 100) },
            { metric: 'Recession P', value: m.recession_prob || 0 },
            { metric: 'Unemployment', value: Math.min((m.unemployment || 4) / 10 * 100, 100) },
            { metric: 'CPI', value: Math.min((m.cpi_yoy || 3) / 8 * 100, 100) },
            { metric: 'Macro Pressure', value: m.macro_pressure_score || 0 },
          ]}>
            <PolarGrid stroke="#374151" />
            <PolarAngleAxis dataKey="metric" tick={{ fontSize: 9, fill: '#9ca3af' }} />
            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 8, fill: '#6b7280' }} />
            <Radar dataKey="value" stroke="#ef4444" fill="#ef4444" fillOpacity={0.25} strokeWidth={2} />
          </RadarChart>
        </ResponsiveContainer>
      </Panel>

      <Panel title="UPST Sensitivity">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div><span className="text-terminal-muted">Rate Sensitivity:</span> <span className="font-bold text-terminal-amber">{m.rate_sensitivity}</span></div>
          <div><span className="text-terminal-muted">Credit Sensitivity:</span> <span className="font-bold text-terminal-amber">{m.credit_sensitivity}</span></div>
        </div>
      </Panel>

      <div className="grid grid-cols-2 gap-4">
        <ScoreBar label="Macro Pressure" value={m.macro_pressure_score} inverted />
        <ScoreBar label="Credit Stress" value={m.credit_stress_score} inverted />
      </div>
    </div>
  )
}
