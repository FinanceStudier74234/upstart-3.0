import React from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function QuantPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const spy = analysis.spy_relationship || {}
  const factor = analysis.factor || {}
  const risk = analysis.risk || {}
  const reflex = analysis.reflexivity || {}
  const of = analysis.overfitting || {}

  return (
    <div className="space-y-4">
      <Panel title="SPY Relationship (Full Detail)">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          <div><span className="text-terminal-muted">Beta:</span> {spy.beta?.toFixed(4)}</div>
          <div><span className="text-terminal-muted">Correlation:</span> {spy.correlation?.toFixed(4)}</div>
          <div><span className="text-terminal-muted">Alpha (ann):</span> {spy.alpha_annualized?.toFixed(4)}</div>
          <div><span className="text-terminal-muted">R²:</span> {spy.pct_market_driven?.toFixed(1)}%</div>
          <div><span className="text-terminal-muted">Upside Capture:</span> {spy.upside_capture?.toFixed(1)}%</div>
          <div><span className="text-terminal-muted">Downside Capture:</span> {spy.downside_capture?.toFixed(1)}%</div>
          <div><span className="text-terminal-muted">Rolling Beta (latest):</span> {spy.rolling_beta_latest?.toFixed(3)}</div>
          <div><span className="text-terminal-muted">Rolling Corr (latest):</span> {spy.rolling_corr_latest?.toFixed(3)}</div>
          <div><span className="text-terminal-muted">Beta Mean:</span> {spy.rolling_beta_mean?.toFixed(3)}</div>
          <div><span className="text-terminal-muted">Beta Std:</span> {spy.rolling_beta_std?.toFixed(3)}</div>
          <div><span className="text-terminal-muted">Regime:</span> {spy.regime}</div>
          <div><span className="text-terminal-muted">Ratio Trend:</span> {spy.ratio_trend}</div>
          <div><span className="text-terminal-muted">UPST DD:</span> {spy.upst_drawdown_current?.toFixed(1)}%</div>
          <div><span className="text-terminal-muted">SPY DD:</span> {spy.spy_drawdown_current?.toFixed(1)}%</div>
        </div>
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Factor Exposure">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Market Beta:</span> {factor.market_beta?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Size (SMB):</span> {factor.size_loading?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Value (HML):</span> {factor.value_loading?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Momentum:</span> {factor.momentum_loading?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Quality:</span> {factor.quality_loading?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Volatility:</span> {factor.volatility_loading?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Style:</span> <span className="font-bold">{factor.style}</span></div>
            <div><span className="text-terminal-muted">Size Class:</span> <span className="font-bold">{factor.size}</span></div>
            <div><span className="text-terminal-muted">Factor Tilt:</span> <span className="font-bold">{factor.factor_tilt}</span></div>
            <div><span className="text-terminal-muted">Crowding:</span> {factor.factor_crowding_score?.toFixed(0)}</div>
          </div>
        </Panel>

        <Panel title="Risk Decomposition">
          <div className="space-y-2 text-xs">
            <div><span className="text-terminal-muted">Systematic Risk:</span> {factor.systematic_risk_pct?.toFixed(1)}%</div>
            <div className="score-bar"><div className="score-fill bg-terminal-cyan" style={{width: `${factor.systematic_risk_pct || 0}%`}} /></div>
            <div><span className="text-terminal-muted">Idiosyncratic Risk:</span> {factor.idiosyncratic_risk_pct?.toFixed(1)}%</div>
            <div className="score-bar"><div className="score-fill bg-terminal-amber" style={{width: `${factor.idiosyncratic_risk_pct || 0}%`}} /></div>
            <div className="mt-2">
              <span className="text-terminal-muted">Sector Correlations:</span>
              <div className="grid grid-cols-2 gap-1 mt-1">
                <div>Fintech: {factor.fintech_correlation?.toFixed(2)}</div>
                <div>Banking: {factor.banking_correlation?.toFixed(2)}</div>
                <div>Growth: {factor.growth_correlation?.toFixed(2)}</div>
                <div>Rate Sensitivity: {factor.rate_sensitivity?.toFixed(2)}</div>
              </div>
            </div>
          </div>
        </Panel>
      </div>

      <Panel title="Return Distribution Stats">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Skewness" value={risk.skewness?.toFixed(3)} sub={risk.skewness < -0.5 ? 'Left-skewed' : risk.skewness > 0.5 ? 'Right-skewed' : 'Symmetric'} />
          <Stat label="Kurtosis" value={risk.kurtosis?.toFixed(3)} sub={risk.kurtosis > 3 ? 'Fat tails' : 'Normal tails'} />
          <Stat label="Tail Ratio" value={risk.tail_ratio?.toFixed(3)} sub={risk.tail_ratio > 1 ? 'Right tail heavier' : 'Left tail heavier'} />
          <Stat label="Max DD" value={`${risk.max_drawdown?.toFixed(1)}%`} color="text-terminal-red" />
        </div>
      </Panel>

      <Panel title="Reflexivity / Feedback Loops">
        <ScoreBar label="Reflexivity Score" value={reflex.reflexivity_score} />
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div><span className="text-terminal-muted">Bullish Spiral Risk:</span> {reflex.bullish_spiral_risk?.toFixed(0)}</div>
          <div><span className="text-terminal-muted">Bearish Spiral Risk:</span> {reflex.bearish_spiral_risk?.toFixed(0)}</div>
          <div><span className="text-terminal-muted">Herding Score:</span> {reflex.herding_score?.toFixed(0)}</div>
          <div><span className="text-terminal-muted">Regime Transition:</span> {reflex.regime_transition_probability?.toFixed(0)}%</div>
        </div>
        {reflex.feedback_loops && reflex.feedback_loops.length > 0 && (
          <div className="mt-3 space-y-2">
            {reflex.feedback_loops.map((l, i) => (
              <div key={i} className="p-2 bg-terminal-bg rounded text-[10px]">
                <div className="flex justify-between">
                  <span className="font-bold">{l.name}</span>
                  <span className={l.current_state === 'active' ? 'text-terminal-red' : l.current_state === 'activating' ? 'text-terminal-amber' : 'text-terminal-muted'}>{l.current_state}</span>
                </div>
                <div className="text-terminal-muted">{l.mechanism}</div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Overfitting / False Edge Detection">
        <div className={`p-2 rounded mb-3 text-xs font-bold ${of.risk_level === 'critical' ? 'bg-red-900/30 text-terminal-red' : of.risk_level === 'high' ? 'bg-orange-900/30 text-terminal-amber' : 'bg-green-900/30 text-terminal-green'}`}>
          Risk Level: {of.risk_level?.toUpperCase()}
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div><span className="text-terminal-muted">IS Sharpe:</span> {of.is_sharpe?.toFixed(2)}</div>
          <div><span className="text-terminal-muted">OOS Sharpe:</span> {of.oos_sharpe?.toFixed(2)}</div>
          <div><span className="text-terminal-muted">Sharpe Decay:</span> {of.sharpe_decay_pct?.toFixed(0)}%</div>
          <div><span className="text-terminal-muted">Haircut Sharpe:</span> {of.haircut_sharpe?.toFixed(4)}</div>
          <div><span className="text-terminal-muted">PBO:</span> {of.pbo ? `${(of.pbo * 100).toFixed(0)}%` : '--'}</div>
          <div><span className="text-terminal-muted">DoF Ratio:</span> {of.degrees_of_freedom_ratio?.toFixed(1)}</div>
        </div>
        {of.warnings && of.warnings.length > 0 && (
          <div className="mt-2 space-y-1">
            {of.warnings.map((w, i) => <div key={i} className="text-terminal-amber text-[10px]">- {w}</div>)}
          </div>
        )}
        <div className="mt-3">
          <ScoreBar label="Overfitting Risk" value={of.overfitting_risk_score} inverted />
        </div>
      </Panel>

      <Panel title="Factor Z-Scores (Mean Reversion Signals)">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-[10px] text-terminal-muted">Momentum Z</div>
            <div className={`text-lg font-bold ${Math.abs(factor.momentum_z || 0) > 1.5 ? 'text-terminal-amber' : ''}`}>{factor.momentum_z?.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-[10px] text-terminal-muted">Value Z</div>
            <div className={`text-lg font-bold ${Math.abs(factor.value_z || 0) > 1.5 ? 'text-terminal-amber' : ''}`}>{factor.value_z?.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-[10px] text-terminal-muted">Quality Z</div>
            <div className={`text-lg font-bold ${Math.abs(factor.quality_z || 0) > 1.5 ? 'text-terminal-amber' : ''}`}>{factor.quality_z?.toFixed(2)}</div>
          </div>
        </div>
      </Panel>
    </div>
  )
}
