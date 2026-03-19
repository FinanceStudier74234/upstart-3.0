import React from 'react'
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
