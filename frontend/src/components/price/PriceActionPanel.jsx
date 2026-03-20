import React from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function PriceActionPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const t = analysis.technical || {}
  const price = analysis.price

  // Build MA comparison chart
  const maData = []
  if (t.sma && typeof t.sma === 'object') {
    Object.entries(t.sma).forEach(([period, val]) => {
      if (val != null) maData.push({ name: `SMA ${period}`, value: val, type: 'SMA',
        fill: val < price ? '#10b981' : '#ef4444' })
    })
  }
  if (t.ema && typeof t.ema === 'object') {
    Object.entries(t.ema).forEach(([period, val]) => {
      if (val != null) maData.push({ name: `EMA ${period}`, value: val, type: 'EMA',
        fill: val < price ? '#10b98180' : '#ef444480' })
    })
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="Price" value={`$${price?.toFixed(2)}`} /></Panel>
        <Panel><Stat label="RSI(14)" value={t.rsi?.toFixed(1)} color={t.rsi > 70 ? 'text-terminal-red' : t.rsi < 30 ? 'text-terminal-green' : ''} /></Panel>
        <Panel><Stat label="MACD" value={t.macd_histogram?.toFixed(4)} color={t.macd_histogram > 0 ? 'text-terminal-green' : 'text-terminal-red'} /></Panel>
        <Panel><Stat label="ATR" value={t.atr?.toFixed(2)} sub={t.atr_pct ? `${t.atr_pct.toFixed(1)}%` : ''} /></Panel>
        <Panel><Stat label="ADX" value={t.adx?.toFixed(1)} sub={t.trend_strength} /></Panel>
        <Panel><Stat label="Stoch %K" value={t.stochastic_k?.toFixed(1)} /></Panel>
      </div>

      {/* Moving Averages Chart */}
      {maData.length > 0 && (
        <Panel title="Moving Averages vs Price">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={maData} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
              <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 9 }} angle={-20} textAnchor="end" height={40} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} domain={['auto', 'auto']}
                tickFormatter={(v) => `$${v.toFixed(0)}`} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', fontSize: 11 }}
                formatter={(v) => `$${Number(v).toFixed(2)}`} />
              {price > 0 && (
                <ReferenceLine y={price} stroke="#06b6d4" strokeDasharray="3 3"
                  label={{ value: `Price $${price.toFixed(2)}`, fill: '#06b6d4', fontSize: 10 }} />
              )}
              <Bar dataKey="value" name="MA Value">
                {maData.map((entry, idx) => (
                  <Cell key={idx} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Moving Averages">
          <div className="space-y-1 text-xs">
            {t.sma && Object.entries(t.sma).map(([p, v]) => (
              <div key={p} className="flex justify-between">
                <span className="text-terminal-muted">SMA({p})</span>
                <span className={price > v ? 'text-terminal-green' : 'text-terminal-red'}>${v?.toFixed(2)}</span>
              </div>
            ))}
            {t.ema && Object.entries(t.ema).map(([p, v]) => (
              <div key={`e${p}`} className="flex justify-between">
                <span className="text-terminal-muted">EMA({p})</span>
                <span className={price > v ? 'text-terminal-green' : 'text-terminal-red'}>${v?.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Regime Classification">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Trend:</span> {t.trend_direction} ({t.trend_strength})</div>
            <div><span className="text-terminal-muted">Momentum:</span> {t.momentum_regime}</div>
            <div><span className="text-terminal-muted">Volatility:</span> {t.volatility_regime}</div>
            <div><span className="text-terminal-muted">Range:</span> {t.range_regime}</div>
            <div><span className="text-terminal-muted">Gap Up:</span> {t.gap_up ? 'YES' : 'No'}</div>
            <div><span className="text-terminal-muted">Gap Down:</span> {t.gap_down ? 'YES' : 'No'}</div>
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Bollinger Bands">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Upper:</span> ${t.bollinger_upper?.toFixed(2)}</div>
            <div><span className="text-terminal-muted">Lower:</span> ${t.bollinger_lower?.toFixed(2)}</div>
            <div><span className="text-terminal-muted">%B:</span> {t.bollinger_pct_b?.toFixed(2)}</div>
            <div><span className="text-terminal-muted">Bandwidth:</span> {t.bollinger_bandwidth?.toFixed(2)}%</div>
            <div><span className="text-terminal-muted">VWAP:</span> ${t.vwap?.toFixed(2)}</div>
            <div><span className="text-terminal-muted">VWAP Dev:</span> {t.vwap_deviation?.toFixed(2)}%</div>
          </div>
        </Panel>

        <Panel title="Support / Resistance">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <div className="text-terminal-green text-[10px] mb-1">SUPPORT</div>
              {(t.support_levels || []).map((s, i) => <div key={i}>${s?.toFixed(2)}</div>)}
            </div>
            <div>
              <div className="text-terminal-red text-[10px] mb-1">RESISTANCE</div>
              {(t.resistance_levels || []).map((r, i) => <div key={i}>${r?.toFixed(2)}</div>)}
            </div>
          </div>
        </Panel>
      </div>

      <Panel title="Trading Zones">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <div>
            <div className="text-terminal-green text-[10px] mb-1">BUY ZONES</div>
            {(t.buy_zones || []).map((z, i) => <div key={i}>${z[0]?.toFixed(2)} — ${z[1]?.toFixed(2)}</div>)}
          </div>
          <div>
            <div className="text-terminal-amber text-[10px] mb-1">SELL ZONES</div>
            {(t.sell_zones || []).map((z, i) => <div key={i}>${z[0]?.toFixed(2)} — ${z[1]?.toFixed(2)}</div>)}
          </div>
          <div>
            <div className="text-terminal-red text-[10px] mb-1">SHORT ZONES</div>
            {(t.short_zones || []).length > 0 ? t.short_zones.map((z, i) => <div key={i}>${z[0]?.toFixed(2)} — ${z[1]?.toFixed(2)}</div>) : <div>None</div>}
          </div>
          <div>
            <div className="text-terminal-cyan text-[10px] mb-1">COVER ZONES</div>
            {(t.cover_zones || []).map((z, i) => <div key={i}>${z[0]?.toFixed(2)} — ${z[1]?.toFixed(2)}</div>)}
          </div>
        </div>
      </Panel>

      <ScoreBar label="Technical Strength" value={t.technical_strength_score} />
    </div>
  )
}
