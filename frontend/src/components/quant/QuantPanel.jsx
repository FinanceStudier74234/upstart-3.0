import React from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  ReferenceLine, Cell,
} from 'recharts'
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
  const garch = analysis.garch || {}
  const hmm = analysis.hmm_regime || {}
  const mf = analysis.multifactor || {}
  const vs = analysis.vol_surface || {}
  const micro = analysis.microstructure || {}
  const kalman = analysis.kalman_beta || {}
  const copula = analysis.copula_risk || {}

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

      {/* Factor Exposure Radar */}
      <Panel title="Factor Exposure Radar">
        <ResponsiveContainer width="100%" height={280}>
          <RadarChart data={[
            { factor: 'Market', value: Math.abs(factor.market_beta || 0) * 50 },
            { factor: 'Size', value: Math.abs(factor.size_loading || 0) * 100 },
            { factor: 'Value', value: Math.abs(factor.value_loading || 0) * 100 },
            { factor: 'Momentum', value: Math.abs(factor.momentum_loading || 0) * 100 },
            { factor: 'Quality', value: Math.abs(factor.quality_loading || 0) * 100 },
            { factor: 'Volatility', value: Math.abs(factor.volatility_loading || 0) * 100 },
          ]}>
            <PolarGrid stroke="#374151" />
            <PolarAngleAxis dataKey="factor" tick={{ fontSize: 10, fill: '#9ca3af' }} />
            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 8, fill: '#6b7280' }} />
            <Radar dataKey="value" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.3} strokeWidth={2} />
          </RadarChart>
        </ResponsiveContainer>
      </Panel>

      {/* Factor Z-Score Bar Chart */}
      <Panel title="Factor Z-Scores">
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={[
            { factor: 'Momentum', z: factor.momentum_z || 0 },
            { factor: 'Value', z: factor.value_z || 0 },
            { factor: 'Quality', z: factor.quality_z || 0 },
          ]}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="factor" tick={{ fontSize: 10, fill: '#9ca3af' }} />
            <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} domain={[-3, 3]} />
            <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
              formatter={v => [v.toFixed(3), 'Z-Score']} />
            <ReferenceLine y={0} stroke="#6b7280" />
            <ReferenceLine y={1.5} stroke="#f59e0b" strokeDasharray="3 3" />
            <ReferenceLine y={-1.5} stroke="#f59e0b" strokeDasharray="3 3" />
            <Bar dataKey="z" radius={[4, 4, 0, 0]}>
              {[factor.momentum_z, factor.value_z, factor.quality_z].map((z, i) => (
                <Cell key={i} fill={Math.abs(z || 0) > 1.5 ? '#f59e0b' : '#06b6d4'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Panel>

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

      {/* ── Advanced PhD-Level Analytics ── */}

      {(garch.garch_converged || garch.alpha) && (
        <Panel title="GARCH(1,1) / EGARCH / GJR-GARCH Volatility Model">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            <div><span className="text-terminal-muted">omega:</span> {garch.omega?.toExponential(3)}</div>
            <div><span className="text-terminal-muted">alpha:</span> {garch.alpha?.toFixed(4)}</div>
            <div><span className="text-terminal-muted">beta:</span> {garch.beta?.toFixed(4)}</div>
            <div><span className="text-terminal-muted">Persistence:</span> <span className={garch.persistence > 0.98 ? 'text-terminal-red font-bold' : ''}>{garch.persistence?.toFixed(4)}</span></div>
            <div><span className="text-terminal-muted">Forecast Vol (ann):</span> <span className="font-bold text-terminal-amber">{(garch.forecast_annualized_vol * 100)?.toFixed(1)}%</span></div>
            <div><span className="text-terminal-muted">Unconditional Vol:</span> {garch.unconditional_volatility ? (garch.unconditional_volatility * Math.sqrt(252) * 100).toFixed(1) : '--'}%</div>
            <div><span className="text-terminal-muted">Half-Life:</span> {garch.half_life_days?.toFixed(1)} days</div>
            <div><span className="text-terminal-muted">Vol-of-Vol (ann):</span> {garch.vol_of_vol_annualized ? (garch.vol_of_vol_annualized * 100).toFixed(2) : '--'}%</div>
            <div><span className="text-terminal-muted">Best Model:</span> <span className="font-bold">{garch.best_model}</span></div>
            <div><span className="text-terminal-muted">Vol Regime:</span> <span className={`font-bold ${garch.current_regime === 'crisis_vol' ? 'text-terminal-red' : garch.current_regime === 'high_vol' ? 'text-terminal-amber' : 'text-terminal-green'}`}>{garch.current_regime}</span></div>
          </div>
          {garch.vol_term_structure && (
            <div className="mt-3">
              <div className="text-[10px] text-terminal-muted mb-1">Volatility Term Structure</div>
              <ResponsiveContainer width="100%" height={120}>
                <BarChart data={Object.entries(garch.vol_term_structure).map(([k, v]) => ({ horizon: k, vol: v * 100 }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="horizon" tick={{ fontSize: 9, fill: '#9ca3af' }} />
                  <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} />
                  <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 10 }} formatter={v => [`${v.toFixed(1)}%`, 'Ann. Vol']} />
                  <Bar dataKey="vol" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
      )}

      {(hmm.current_regime || hmm.current_regime_probabilities) && (
        <Panel title="Hidden Markov Model — 3-State Regime Detection">
          {hmm.current_regime_probabilities && (
            <div className="grid grid-cols-3 gap-4 mb-3">
              {Object.entries(hmm.current_regime_probabilities).map(([name, prob], i) => {
                const colors = { bull: 'text-terminal-green', neutral: 'text-terminal-cyan', bear: 'text-terminal-red' }
                const color = colors[name.toLowerCase()] || 'text-terminal-muted'
                return (
                  <div key={name} className={`text-center p-2 rounded ${hmm.current_regime === name ? 'bg-terminal-panel border border-terminal-border' : ''}`}>
                    <div className="text-[10px] text-terminal-muted">{name.toUpperCase()}</div>
                    <div className={`text-xl font-bold ${color}`}>{(prob * 100).toFixed(1)}%</div>
                  </div>
                )
              })}
            </div>
          )}
          {hmm.regime_statistics && hmm.regime_statistics.length > 0 && (
            <div className="grid grid-cols-3 gap-2 text-[9px] text-terminal-muted mb-2">
              {hmm.regime_statistics.map((rs, i) => (
                <div key={i} className="text-center">
                  mu_ann={rs.mean_return_ann?.toFixed(1)}% | vol_ann={rs.vol_ann?.toFixed(1)}%
                </div>
              ))}
            </div>
          )}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Current Regime:</span> <span className="font-bold">{hmm.current_regime?.toUpperCase() || '--'}</span></div>
            <div><span className="text-terminal-muted">Converged:</span> {hmm.converged ? 'Yes' : 'No'} ({hmm.iterations} iters)</div>
            {hmm.regime_change_alerts && hmm.regime_change_alerts.length > 0 && (
              <div className="col-span-2 text-terminal-red font-bold">REGIME CHANGE DETECTED</div>
            )}
          </div>
          {hmm.expected_regime_duration && (
            <div className="mt-2 text-[10px] text-terminal-muted">
              Expected durations: {Object.entries(hmm.expected_regime_duration).map(([k, v]) => `${k}=${v.toFixed(0)}d`).join(', ')}
            </div>
          )}
        </Panel>
      )}

      {kalman.current_beta !== undefined && (
        <Panel title="Kalman Filter — Time-Varying Beta">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            <div><span className="text-terminal-muted">Kalman Beta:</span> <span className="font-bold text-terminal-cyan">{kalman.current_beta?.toFixed(4)}</span></div>
            <div><span className="text-terminal-muted">Beta Std:</span> {kalman.beta_std?.toFixed(4)}</div>
            <div><span className="text-terminal-muted">5d Forecast:</span> {kalman.beta_forecast_5d?.toFixed(4)}</div>
            <div><span className="text-terminal-muted">21d Forecast:</span> {kalman.beta_forecast_21d?.toFixed(4)}</div>
            <div><span className="text-terminal-muted">Filtered Alpha:</span> {kalman.alpha_filtered?.toFixed(4)}</div>
            <div><span className="text-terminal-muted">R² (filtered):</span> {kalman.r_squared_filtered?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Structural Breaks:</span> <span className={kalman.structural_breaks?.length > 0 ? 'text-terminal-red' : ''}>{kalman.structural_breaks?.length || 0}</span></div>
          </div>
        </Panel>
      )}

      {(copula.lambda_lower !== undefined || copula.conditional_var_5pct) && (
        <Panel title="Copula Tail Risk (UPST vs SPY)">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
            <div><span className="text-terminal-muted">Lower Tail Dep (lambda_L):</span> <span className="font-bold text-terminal-red">{copula.lambda_lower?.toFixed(4)}</span></div>
            <div><span className="text-terminal-muted">Upper Tail Dep (lambda_U):</span> <span className="font-bold text-terminal-green">{copula.lambda_upper?.toFixed(4)}</span></div>
            <div><span className="text-terminal-muted">Student-t DoF:</span> {copula.student_t_df?.toFixed(1)}</div>
            <div><span className="text-terminal-muted">Cond. VaR (SPY@5%):</span> <span className="text-terminal-red">{copula.conditional_var_5pct ? (copula.conditional_var_5pct * 100).toFixed(1) : '--'}%</span></div>
            <div><span className="text-terminal-muted">Joint DD (10%/5%):</span> <span className="text-terminal-red">{copula.joint_drawdown_prob_10_5 ? (copula.joint_drawdown_prob_10_5 * 100).toFixed(2) : '--'}%</span></div>
            <div><span className="text-terminal-muted">Portfolio VaR (copula):</span> {copula.portfolio_var_with_copula ? (copula.portfolio_var_with_copula * 100).toFixed(1) : '--'}%</div>
          </div>
          <div className="mt-2 text-[10px] text-terminal-muted">
            Non-zero tail dependence = correlation increases in crashes. Gaussian copula assumes lambda=0 (dangerous).
          </div>
        </Panel>
      )}

      {micro.kyle_lambda !== undefined && (
        <Panel title="Microstructure Intelligence">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
            <div><span className="text-terminal-muted">Kyle Lambda:</span> {micro.kyle_lambda?.toExponential(3)}</div>
            <div><span className="text-terminal-muted">Amihud Illiquidity:</span> {micro.amihud_illiquidity?.toExponential(3)}</div>
            <div><span className="text-terminal-muted">VPIN:</span> <span className={micro.vpin > 0.7 ? 'text-terminal-red font-bold' : ''}>{micro.vpin?.toFixed(3)}</span></div>
            <div><span className="text-terminal-muted">Roll Spread:</span> {(micro.roll_spread * 100)?.toFixed(3)}%</div>
            <div><span className="text-terminal-muted">CS Spread:</span> {(micro.corwin_schultz_spread * 100)?.toFixed(3)}%</div>
            <div><span className="text-terminal-muted">Flow Toxicity:</span> <span className={`font-bold ${micro.flow_toxicity_regime === 'toxic' ? 'text-terminal-red' : micro.flow_toxicity_regime === 'elevated' ? 'text-terminal-amber' : 'text-terminal-green'}`}>{micro.flow_toxicity_regime}</span></div>
          </div>
        </Panel>
      )}

      {vs.surface_regime && (
        <Panel title="Volatility Surface (SABR)">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            <div><span className="text-terminal-muted">Surface Regime:</span> <span className="font-bold">{vs.surface_regime}</span></div>
            <div><span className="text-terminal-muted">25d Risk Reversal:</span> {vs.risk_reversal_25d?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Butterfly:</span> {vs.butterfly_25d?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Term Slope:</span> {vs.term_structure_slope}</div>
            <div><span className="text-terminal-muted">SABR rho:</span> {vs.sabr_rho?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">SABR nu (volvol):</span> {vs.sabr_nu?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Sticky Mode:</span> {vs.sticky_mode}</div>
          </div>
        </Panel>
      )}

      {mf.r_squared !== undefined && (
        <Panel title="Multi-Factor Regression (Fama-French Style)">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs mb-2">
            <div><span className="text-terminal-muted">R²:</span> {mf.r_squared?.toFixed(4)}</div>
            <div><span className="text-terminal-muted">Adj R²:</span> {mf.adj_r_squared?.toFixed(4)}</div>
            <div><span className="text-terminal-muted">JB Normality p:</span> {mf.jarque_bera_p?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Durbin-Watson:</span> {mf.durbin_watson?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Systematic Risk:</span> {mf.systematic_risk_pct?.toFixed(1)}%</div>
            <div><span className="text-terminal-muted">Idiosyncratic Risk:</span> {mf.idiosyncratic_risk_pct?.toFixed(1)}%</div>
            <div><span className="text-terminal-muted">Alpha (ann):</span> {mf.alpha_annualized?.toFixed(4)}</div>
            <div><span className="text-terminal-muted">Style:</span> <span className="font-bold">{mf.style_classification}</span></div>
          </div>
          {mf.betas && (
            <div className="space-y-1 text-[10px]">
              <div className="text-terminal-muted font-bold mb-1">Factor Loadings:</div>
              {Object.entries(mf.betas).map(([name, beta]) => (
                <div key={name} className="flex justify-between">
                  <span>{name}</span>
                  <span className={mf.p_values?.[name] < 0.05 ? 'font-bold text-terminal-cyan' : 'text-terminal-muted'}>
                    beta={beta?.toFixed(4)} (t={mf.t_stats?.[name]?.toFixed(2)}, p={mf.p_values?.[name]?.toFixed(3)})
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}
    </div>
  )
}
