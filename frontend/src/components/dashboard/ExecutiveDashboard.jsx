import React, { useMemo } from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, Cell,
  ComposedChart, Area, Line, ReferenceLine,
} from 'recharts'

export default function ExecutiveDashboard({ analysis }) {
  const isMockData = analysis?.data_sources && Object.values(analysis.data_sources).some(s => s === 'mock')

  if (!analysis) return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="panel p-3 animate-pulse">
            <div className="h-3 bg-terminal-border/30 rounded w-20 mb-2" />
            <div className="h-6 bg-terminal-border/30 rounded w-16" />
          </div>
        ))}
      </div>
    </div>
  )

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

  // Trade levels data for visual entry/target/stop chart
  const tradeLevelsData = useMemo(() => {
    if (!decision.entry_price) return null
    const entry = decision.entry_price
    const target = decision.target_price
    const stop = decision.stop_price
    if (!target || !stop) return null
    const isBullish = target > entry
    const allPrices = [entry, target, stop].filter(Boolean)
    const min = Math.min(...allPrices) * 0.98
    const max = Math.max(...allPrices) * 1.02
    return { entry, target, stop, min, max, isBullish }
  }, [decision])

  // Forecast cone data
  const forecastConeData = useMemo(() => {
    if (!fc.models || !price) return []
    const models = fc.models || []
    const points = models.map(m => ({
      name: m.name?.replace(/Engine|Model/g, '').trim() || 'Unknown',
      lower: m.lower,
      point: m.point,
      upper: m.upper,
    })).filter(m => m.point != null)
    if (fc.ensemble_point) {
      points.push({
        name: 'Ensemble',
        lower: fc.ensemble_lower,
        point: fc.ensemble_point,
        upper: fc.ensemble_upper,
      })
    }
    return points
  }, [fc, price])

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
      {isMockData && (
        <div className="mb-3 px-3 py-2 bg-terminal-amber/10 border border-terminal-amber/30 rounded text-xs text-terminal-amber">
          Running on simulated data. Connect API keys for live market data.
        </div>
      )}
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

      {/* Scores Grid — with expandable component breakdown */}
      <Panel title="Composite Scores">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {scores && Object.entries(scores).map(([k, v]) => (
            <ScoreBar
              key={k}
              label={k.replace(/_/g, ' ')}
              value={v?.value}
              inverted={invertedScores.includes(k)}
              components={v?.components}
              confidence={v?.confidence}
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

      {/* Trade Decision + Trade Levels Visual */}
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

        {/* Trade Levels Visual */}
        {tradeLevelsData ? (
          <Panel title="Trade Levels">
            <div className="relative h-48 flex items-stretch">
              {/* Price axis */}
              <div className="flex flex-col justify-between w-full relative">
                {/* Target zone */}
                <div className="absolute left-0 right-0" style={{
                  top: `${(1 - (tradeLevelsData.target - tradeLevelsData.min) / (tradeLevelsData.max - tradeLevelsData.min)) * 100}%`,
                }}>
                  <div className="flex items-center gap-2">
                    <div className={`h-px flex-1 ${tradeLevelsData.isBullish ? 'bg-terminal-green' : 'bg-terminal-red'}`} />
                    <span className={`text-[10px] font-bold ${tradeLevelsData.isBullish ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      TARGET ${tradeLevelsData.target.toFixed(2)}
                    </span>
                  </div>
                </div>
                {/* Entry zone */}
                <div className="absolute left-0 right-0" style={{
                  top: `${(1 - (tradeLevelsData.entry - tradeLevelsData.min) / (tradeLevelsData.max - tradeLevelsData.min)) * 100}%`,
                }}>
                  <div className="flex items-center gap-2">
                    <div className="h-px flex-1 bg-terminal-cyan border-dashed" />
                    <span className="text-[10px] font-bold text-terminal-cyan">
                      ENTRY ${tradeLevelsData.entry.toFixed(2)}
                    </span>
                  </div>
                </div>
                {/* Stop zone */}
                <div className="absolute left-0 right-0" style={{
                  top: `${(1 - (tradeLevelsData.stop - tradeLevelsData.min) / (tradeLevelsData.max - tradeLevelsData.min)) * 100}%`,
                }}>
                  <div className="flex items-center gap-2">
                    <div className={`h-px flex-1 ${tradeLevelsData.isBullish ? 'bg-terminal-red' : 'bg-terminal-green'}`} />
                    <span className={`text-[10px] font-bold ${tradeLevelsData.isBullish ? 'text-terminal-red' : 'text-terminal-green'}`}>
                      STOP ${tradeLevelsData.stop.toFixed(2)}
                    </span>
                  </div>
                </div>
                {/* Reward/Risk zones with gradient */}
                <div className="absolute left-4 w-8 rounded opacity-30" style={{
                  top: `${(1 - (Math.max(tradeLevelsData.entry, tradeLevelsData.target) - tradeLevelsData.min) / (tradeLevelsData.max - tradeLevelsData.min)) * 100}%`,
                  bottom: `${((Math.min(tradeLevelsData.entry, tradeLevelsData.target) - tradeLevelsData.min) / (tradeLevelsData.max - tradeLevelsData.min)) * 100}%`,
                  backgroundColor: tradeLevelsData.isBullish ? '#10b981' : '#ef4444',
                }} />
                <div className="absolute left-4 w-8 rounded opacity-30" style={{
                  top: `${(1 - (Math.max(tradeLevelsData.entry, tradeLevelsData.stop) - tradeLevelsData.min) / (tradeLevelsData.max - tradeLevelsData.min)) * 100}%`,
                  bottom: `${((Math.min(tradeLevelsData.entry, tradeLevelsData.stop) - tradeLevelsData.min) / (tradeLevelsData.max - tradeLevelsData.min)) * 100}%`,
                  backgroundColor: tradeLevelsData.isBullish ? '#ef4444' : '#10b981',
                }} />
              </div>
            </div>
            {decision.reward_risk_ratio && (
              <div className="mt-2 text-center text-xs text-terminal-muted">
                Reward:Risk = <span className="font-bold text-terminal-cyan">{decision.reward_risk_ratio.toFixed(2)}:1</span>
                {decision.expected_value != null && (
                  <span className="ml-3">EV = <span className={decision.expected_value >= 0 ? 'text-terminal-green' : 'text-terminal-red'}>
                    ${decision.expected_value.toFixed(2)}
                  </span></span>
                )}
              </div>
            )}
          </Panel>
        ) : (
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
        )}
      </div>

      {/* Forecast Cone Chart + Text */}
      <Panel title="Ensemble Forecast">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs mb-4">
          <Stat label="Point Estimate" value={fc.ensemble_point ? `$${fc.ensemble_point}` : '--'} />
          <Stat label="Lower (80%)" value={fc.ensemble_lower ? `$${fc.ensemble_lower}` : '--'} />
          <Stat label="Upper (80%)" value={fc.ensemble_upper ? `$${fc.ensemble_upper}` : '--'} />
          <Stat label="Model Agreement" value={fc.model_agreement ? `${(fc.model_agreement * 100).toFixed(0)}%` : '--'} />
          <Stat label="Confidence" value={fc.confidence_score?.toFixed(0)} />
        </div>
        {forecastConeData.length > 0 && (
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
            <h3 className="text-xs font-bold text-gray-300 mb-2 uppercase tracking-wider">Model Forecast Comparison</h3>
            <ResponsiveContainer width="100%" height={200}>
              <ComposedChart data={forecastConeData} margin={{ top: 10, right: 30, left: 10, bottom: 5 }}>
                <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 9 }} axisLine={{ stroke: '#374151' }} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 9 }} axisLine={{ stroke: '#374151' }}
                  domain={['auto', 'auto']} tickFormatter={(v) => `$${v}`} />
                <Tooltip contentStyle={CustomTooltipStyle} formatter={(val) => [`$${val?.toFixed(2)}`, '']} />
                {price && <ReferenceLine y={price} stroke="#06b6d4" strokeDasharray="3 3"
                  label={{ value: `Current $${price.toFixed(2)}`, fill: '#06b6d4', fontSize: 9, position: 'right' }} />}
                <Area dataKey="lower" stackId="range" fill="transparent" stroke="transparent" />
                <Area dataKey="upper" stackId="range" fill="#10b981" fillOpacity={0.15} stroke="transparent" />
                <Line dataKey="point" stroke="#10b981" strokeWidth={2} dot={{ r: 4, fill: '#10b981' }} />
                <Line dataKey="lower" stroke="#374151" strokeWidth={1} strokeDasharray="3 3" dot={false} />
                <Line dataKey="upper" stroke="#374151" strokeWidth={1} strokeDasharray="3 3" dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
        {fc.models && !forecastConeData.length && (
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
