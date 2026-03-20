import React, { useMemo } from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, Cell
} from 'recharts'

export default function ExecutiveDashboard({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-8">Loading analysis...</div>

  const { price, scores, trade_decision, forecast, spy_relationship, short, options, risk, technical } = analysis

  const decision = trade_decision || {}
  const fc = forecast || {}

  const priceColor = (decision.action || '').includes('buy') ? 'text-terminal-green'
    : (decision.action || '').includes('short') ? 'text-terminal-red' : 'text-terminal-text'

  const invertedScores = ['macro_pressure', 'credit_stress', 'squeeze_risk', 'positioning_fragility']

  const radarData = useMemo(() => {
    if (!scores) return []
    return Object.entries(scores).map(([k, v]) => ({
      subject: k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      value: v?.value != null ? Math.round(v.value) : 0,
      fullMark: 100,
    }))
  }, [scores])

  const barData = useMemo(() => {
    if (!scores) return []
    return Object.entries(scores).map(([k, v]) => {
      const raw = v?.value != null ? Math.round(v.value) : 0
      const isInverted = invertedScores.includes(k)
      return {
        name: k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        score: raw,
        fill: isInverted ? (raw > 50 ? '#ef4444' : '#10b981') : (raw >= 50 ? '#10b981' : '#ef4444'),
      }
    })
  }, [scores])

  const CustomTooltipStyle = {
    backgroundColor: '#1f2937',
    border: '1px solid #374151',
    borderRadius: '6px',
    color: '#d1d5db',
    fontSize: '11px',
    padding: '6px 10px',
  }

  return (
    <div className="space-y-4">
      {/* Header Row */}
      <div className="flex items-center gap-4 px-1">
        <h1 className="text-2xl font-black text-terminal-cyan">UPST</h1>
        <span className={`text-3xl font-black ${priceColor}`}>${price?.toFixed(2) || '--'}</span>
        <span className="text-terminal-muted text-xs">Upstart Holdings, Inc.</span>
        <div className="ml-auto text-[10px] text-terminal-muted">
          Updated: {analysis.timestamp?.slice(0, 19) || 'N/A'}
        </div>
      </div>

      {/* Top Row: Key Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
        <Panel><Stat label="Price" value={`$${price?.toFixed(2)}`} color={priceColor} /></Panel>
        <Panel><Stat label="Action" value={decision.action?.toUpperCase()} color={
          (decision.action || '').includes('buy') ? 'text-terminal-green' :
          (decision.action || '').includes('short') ? 'text-terminal-red' : 'text-terminal-amber'
        } /></Panel>
        <Panel><Stat label="Vehicle" value={decision.vehicle} /></Panel>
        <Panel><Stat label="Confidence" value={decision.confidence} /></Panel>
        <Panel><Stat label="Forecast" value={fc.ensemble_point ? `$${fc.ensemble_point}` : '--'} /></Panel>
        <Panel><Stat label="Beta vs SPY" value={spy_relationship?.beta?.toFixed(2)} /></Panel>
        <Panel><Stat label="Squeeze Risk" value={short?.squeeze_risk_score?.toFixed(0)} color={
          (short?.squeeze_risk_score || 0) > 70 ? 'text-terminal-red' : 'text-terminal-text'
        } /></Panel>
        <Panel><Stat label="ATM IV" value={options?.atm_iv ? `${(options.atm_iv * 100).toFixed(0)}%` : '--'} /></Panel>
      </div>

      {/* Scores Grid */}
      <Panel title="Composite Scores">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {scores && Object.entries(scores).map(([k, v]) => (
            <ScoreBar
              key={k}
              label={k.replace(/_/g, ' ')}
              value={v?.value}
              inverted={invertedScores.includes(k)}
            />
          ))}
        </div>

        {/* Charts Row */}
        {radarData.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
            {/* Radar Chart */}
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
              <h3 className="text-xs font-bold text-gray-300 mb-2 uppercase tracking-wider">Score Radar</h3>
              <ResponsiveContainer width="100%" height={320}>
                <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
                  <PolarGrid stroke="#374151" />
                  <PolarAngleAxis
                    dataKey="subject"
                    tick={{ fill: '#9ca3af', fontSize: 9 }}
                  />
                  <PolarRadiusAxis
                    angle={90}
                    domain={[0, 100]}
                    tick={{ fill: '#6b7280', fontSize: 9 }}
                    axisLine={false}
                  />
                  <Radar
                    name="Score"
                    dataKey="value"
                    stroke="#10b981"
                    fill="#10b981"
                    fillOpacity={0.25}
                  />
                  <Tooltip
                    contentStyle={CustomTooltipStyle}
                    formatter={(val) => [`${val} / 100`, 'Score']}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* Bar Chart */}
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
              <h3 className="text-xs font-bold text-gray-300 mb-2 uppercase tracking-wider">Metrics Comparison</h3>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart
                  data={barData}
                  layout="vertical"
                  margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                >
                  <XAxis
                    type="number"
                    domain={[0, 100]}
                    tick={{ fill: '#9ca3af', fontSize: 10 }}
                    axisLine={{ stroke: '#374151' }}
                    tickLine={{ stroke: '#374151' }}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fill: '#9ca3af', fontSize: 9 }}
                    width={120}
                    axisLine={{ stroke: '#374151' }}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={CustomTooltipStyle}
                    formatter={(val) => [`${val} / 100`, 'Score']}
                    cursor={{ fill: 'rgba(55, 65, 81, 0.4)' }}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: '10px', color: '#9ca3af' }}
                  />
                  <Bar
                    dataKey="score"
                    name="Score"
                    radius={[0, 4, 4, 0]}
                    barSize={14}
                    isAnimationActive={true}
                  >
                    {barData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </Panel>

      {/* Trade Decision Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Trade Decision">
          <div className="space-y-2 text-xs">
            <div><span className="text-terminal-muted">Action:</span> <span className="font-bold">{decision.action}</span></div>
            <div><span className="text-terminal-muted">Vehicle:</span> {decision.vehicle}</div>
            <div><span className="text-terminal-muted">Entry:</span> ${decision.entry_price?.toFixed(2)}</div>
            <div><span className="text-terminal-muted">Target:</span> ${decision.target_price?.toFixed(2)}</div>
            <div><span className="text-terminal-muted">Stop:</span> ${decision.stop_price?.toFixed(2)}</div>
            <div><span className="text-terminal-muted">R:R:</span> {decision.reward_risk_ratio?.toFixed(2)}</div>
            <div><span className="text-terminal-muted">Size:</span> {decision.suggested_position_pct?.toFixed(1)}%</div>
            <div className="mt-2 p-2 bg-terminal-bg rounded text-terminal-muted">{decision.explanation}</div>
            {decision.what_would_change && (
              <div className="p-2 bg-terminal-bg rounded text-terminal-amber text-[10px]">
                <strong>What would change:</strong> {decision.what_would_change}
              </div>
            )}
            {decision.risk_factors?.length > 0 && (
              <div className="p-2 bg-terminal-bg rounded text-terminal-red text-[10px]">
                <strong>Risks:</strong> {decision.risk_factors.join('; ')}
              </div>
            )}
          </div>
        </Panel>

        <Panel title="SPY Relationship">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Beta:</span> {spy_relationship?.beta?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Correlation:</span> {spy_relationship?.correlation?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">Alpha (ann):</span> {spy_relationship?.alpha_annualized?.toFixed(3)}</div>
            <div><span className="text-terminal-muted">R²:</span> {spy_relationship?.pct_market_driven?.toFixed(1)}%</div>
            <div><span className="text-terminal-muted">Upside Capture:</span> {spy_relationship?.upside_capture?.toFixed(1)}%</div>
            <div><span className="text-terminal-muted">Downside Capture:</span> {spy_relationship?.downside_capture?.toFixed(1)}%</div>
            <div><span className="text-terminal-muted">Regime:</span> {spy_relationship?.regime}</div>
            <div><span className="text-terminal-muted">Ratio Trend:</span> {spy_relationship?.ratio_trend}</div>
            <div><span className="text-terminal-muted">UPST DD:</span> {spy_relationship?.upst_drawdown_current?.toFixed(1)}%</div>
            <div><span className="text-terminal-muted">SPY DD:</span> {spy_relationship?.spy_drawdown_current?.toFixed(1)}%</div>
          </div>
        </Panel>
      </div>

      {/* Forecast */}
      <Panel title="Ensemble Forecast">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
          <Stat label="Point Estimate" value={fc.ensemble_point ? `$${fc.ensemble_point}` : '--'} />
          <Stat label="Lower (80%)" value={fc.ensemble_lower ? `$${fc.ensemble_lower}` : '--'} />
          <Stat label="Upper (80%)" value={fc.ensemble_upper ? `$${fc.ensemble_upper}` : '--'} />
          <Stat label="Model Agreement" value={fc.model_agreement ? `${(fc.model_agreement * 100).toFixed(0)}%` : '--'} />
          <Stat label="Confidence" value={fc.confidence_score?.toFixed(0)} />
        </div>
        {fc.models && (
          <div className="mt-3 space-y-1">
            {fc.models.map((m, i) => (
              <div key={i} className="flex gap-4 text-[10px] text-terminal-muted">
                <span className="w-32">{m.name}</span>
                <span>${m.point?.toFixed(2)}</span>
                <span className="text-terminal-muted">[${m.lower?.toFixed(2)} — ${m.upper?.toFixed(2)}]</span>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {/* Short Intelligence */}
      <Panel title="Short / Squeeze Intelligence">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          <div><span className="text-terminal-muted">SI % Float:</span> {short?.short_pct_float?.toFixed(1)}%</div>
          <div><span className="text-terminal-muted">Days to Cover:</span> {short?.days_to_cover?.toFixed(1)}</div>
          <div><span className="text-terminal-muted">Cost to Borrow:</span> {short?.cost_to_borrow?.toFixed(1)}%</div>
          <div><span className="text-terminal-muted">Utilization:</span> {short?.utilization?.toFixed(0)}%</div>
          <div><span className="text-terminal-muted">Squeeze Score:</span>
            <span className={(short?.squeeze_risk_score || 0) > 70 ? 'text-terminal-red font-bold' : ''}>
              {' '}{short?.squeeze_risk_score?.toFixed(0)}
            </span>
          </div>
          <div><span className="text-terminal-muted">Short Decision:</span> {short?.short_decision}</div>
          <div><span className="text-terminal-muted">Do Not Short:</span>
            <span className={short?.do_not_short_flag ? 'text-terminal-red font-bold' : 'text-terminal-green'}>
              {' '}{short?.do_not_short_flag ? 'YES' : 'NO'}
            </span>
          </div>
          <div><span className="text-terminal-muted">Best Vehicle:</span> {short?.best_bearish_vehicle}</div>
        </div>
        {short?.short_decision_explanation && (
          <div className="mt-2 p-2 bg-terminal-bg rounded text-[10px] text-terminal-muted">
            {short.short_decision_explanation}
          </div>
        )}
      </Panel>

      {/* Risk */}
      <Panel title="Risk Metrics">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          <Stat label="VaR 95% (1d)" value={risk?.var_95_1d ? `$${risk.var_95_1d.toFixed(2)}` : '--'} />
          <Stat label="CVaR 95%" value={risk?.cvar_95_1d ? `$${risk.cvar_95_1d.toFixed(2)}` : '--'} />
          <Stat label="Max DD" value={risk?.max_drawdown ? `${risk.max_drawdown.toFixed(1)}%` : '--'} color="text-terminal-red" />
          <Stat label="Recommended Size" value={risk?.recommended_size_pct ? `${risk.recommended_size_pct.toFixed(1)}%` : '--'} />
          <Stat label="Quarter Kelly" value={risk?.quarter_kelly_pct ? `${risk.quarter_kelly_pct.toFixed(1)}%` : '--'} />
          <Stat label="Risk of Ruin" value={risk?.risk_of_ruin_pct ? `${risk.risk_of_ruin_pct.toFixed(2)}%` : '--'} />
          <Stat label="Skewness" value={risk?.skewness?.toFixed(2)} />
          <Stat label="Kurtosis" value={risk?.kurtosis?.toFixed(2)} />
        </div>
      </Panel>

      {/* Data Governance */}
      {analysis.data_governance && (
        <Panel title="Data Governance">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-2">
            <Stat label="Quality Score" value={analysis.data_governance.overall_quality_score?.toFixed(0)} />
            <Stat label="Freshness" value={`${analysis.data_governance.overall_freshness_score?.toFixed(0)}%`} />
            <Stat label="Coverage" value={`${analysis.data_governance.overall_coverage_pct?.toFixed(0)}%`} />
            <Stat label="Snooping Risk" value={analysis.data_governance.data_snooping_risk?.toFixed(0)}
              color={analysis.data_governance.data_snooping_risk > 50 ? 'text-terminal-red' : ''} />
          </div>
          {analysis.data_governance.stale_sources?.length > 0 && (
            <div className="text-[10px] text-terminal-amber mt-1">
              Stale: {analysis.data_governance.stale_sources.join(', ')}
            </div>
          )}
          {analysis.data_governance.recommendations?.length > 0 && (
            <div className="mt-2 space-y-1">
              {analysis.data_governance.recommendations.slice(0, 3).map((r, i) => (
                <div key={i} className="text-[10px] text-terminal-muted">• {r}</div>
              ))}
            </div>
          )}
        </Panel>
      )}

      {/* Data Sources */}
      <div className="flex flex-wrap gap-2 text-[10px] text-terminal-muted px-1">
        {analysis.data_sources && Object.entries(analysis.data_sources).map(([k, v]) => (
          <span key={k} className="bg-terminal-panel px-2 py-0.5 rounded">{k}: {v}</span>
        ))}
        {analysis.warnings?.length > 0 && (
          <span className="text-terminal-amber">
            {analysis.warnings.length} warning(s)
          </span>
        )}
      </div>
    </div>
  )
}
