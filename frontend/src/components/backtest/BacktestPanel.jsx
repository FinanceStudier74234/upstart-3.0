import React, { useState } from 'react'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine,
} from 'recharts'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import { api } from '../../services/api'

export default function BacktestPanel() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [params, setParams] = useState({
    strategy: 'technical_signals',
    days: 365,
    position_size_pct: 10,
    stop_loss_pct: 5,
    take_profit_pct: 10,
  })

  const runBacktest = async () => {
    setLoading(true)
    try {
      const res = await api.runBacktest(params)
      setResult(res)
    } catch (e) {
      setResult({ error: e.message })
    }
    setLoading(false)
  }

  return (
    <div className="space-y-4">
      <Panel title="Backtest Configuration">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div>
            <label className="text-[10px] text-terminal-muted">Strategy</label>
            <select value={params.strategy} onChange={e => setParams({...params, strategy: e.target.value})}
              className="w-full bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-xs">
              <option value="technical_signals">Technical Signals (RSI)</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] text-terminal-muted">Lookback (days)</label>
            <input type="number" value={params.days} onChange={e => setParams({...params, days: +e.target.value})}
              className="w-full bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-xs" />
          </div>
          <div>
            <label className="text-[10px] text-terminal-muted">Position Size %</label>
            <input type="number" value={params.position_size_pct} onChange={e => setParams({...params, position_size_pct: +e.target.value})}
              className="w-full bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-xs" />
          </div>
          <div>
            <label className="text-[10px] text-terminal-muted">Stop Loss %</label>
            <input type="number" value={params.stop_loss_pct} onChange={e => setParams({...params, stop_loss_pct: +e.target.value})}
              className="w-full bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-xs" />
          </div>
          <div>
            <label className="text-[10px] text-terminal-muted">Take Profit %</label>
            <input type="number" value={params.take_profit_pct} onChange={e => setParams({...params, take_profit_pct: +e.target.value})}
              className="w-full bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-xs" />
          </div>
        </div>
        <button onClick={runBacktest} disabled={loading}
          className="mt-3 px-4 py-2 bg-terminal-cyan text-terminal-bg font-bold text-xs rounded hover:opacity-80 disabled:opacity-40">
          {loading ? 'Running...' : 'Run Backtest'}
        </button>
      </Panel>

      {result && !result.error && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <Panel><Stat label="Total Return" value={`${result.total_return?.toFixed(1)}%`} color={result.total_return > 0 ? 'text-terminal-green' : 'text-terminal-red'} /></Panel>
            <Panel><Stat label="Sharpe" value={result.sharpe_ratio?.toFixed(2)} /></Panel>
            <Panel><Stat label="Sortino" value={result.sortino_ratio?.toFixed(2)} /></Panel>
            <Panel><Stat label="Calmar" value={result.calmar_ratio?.toFixed(2)} /></Panel>
            <Panel><Stat label="Max DD" value={`${result.max_drawdown?.toFixed(1)}%`} color="text-terminal-red" /></Panel>
            <Panel><Stat label="Win Rate" value={`${result.win_rate?.toFixed(0)}%`} /></Panel>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Panel title="Trade Statistics">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div><span className="text-terminal-muted">Total Trades:</span> {result.total_trades}</div>
                <div><span className="text-terminal-muted">Win Rate:</span> {result.win_rate?.toFixed(1)}%</div>
                <div><span className="text-terminal-muted">Avg Win:</span> <span className="text-terminal-green">{result.avg_win?.toFixed(2)}%</span></div>
                <div><span className="text-terminal-muted">Avg Loss:</span> <span className="text-terminal-red">{result.avg_loss?.toFixed(2)}%</span></div>
                <div><span className="text-terminal-muted">Payoff Ratio:</span> {result.payoff_ratio?.toFixed(2)}</div>
                <div><span className="text-terminal-muted">Expectancy:</span> {result.expectancy?.toFixed(2)}%</div>
                <div><span className="text-terminal-muted">Profit Factor:</span> {result.profit_factor?.toFixed(2)}</div>
                <div><span className="text-terminal-muted">Ann. Return:</span> {result.annualized_return?.toFixed(1)}%</div>
              </div>
            </Panel>

            <Panel title="Alpha / Beta Decomposition">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div><span className="text-terminal-muted">Alpha vs SPY:</span> <span className={result.alpha_vs_spy > 0 ? 'text-terminal-green' : 'text-terminal-red'}>{result.alpha_vs_spy?.toFixed(4)}</span></div>
                <div><span className="text-terminal-muted">Beta vs SPY:</span> {result.beta_vs_spy?.toFixed(4)}</div>
              </div>
            </Panel>
          </div>

          {/* Equity Curve Chart */}
          {result.equity_curve && result.equity_curve.length > 1 && (
            <Panel title="Equity Curve">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={result.equity_curve.map((v, i) => ({ idx: i, equity: v }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="idx" tick={{ fontSize: 9, fill: '#9ca3af' }} />
                  <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} domain={['auto', 'auto']}
                    tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                  <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
                    formatter={v => [`$${v.toLocaleString()}`, 'Equity']} />
                  <Line type="monotone" dataKey="equity" stroke="#06b6d4" strokeWidth={2} dot={false} />
                  <ReferenceLine y={100000} stroke="#6b7280" strokeDasharray="3 3" label={{ value: 'Start', fill: '#6b7280', fontSize: 9 }} />
                </LineChart>
              </ResponsiveContainer>
            </Panel>
          )}

          {/* Drawdown Chart */}
          {result.drawdown_series && result.drawdown_series.length > 1 && (
            <Panel title="Drawdown">
              <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={result.drawdown_series.map((v, i) => ({ idx: i, dd: v }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="idx" tick={{ fontSize: 9, fill: '#9ca3af' }} />
                  <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} tickFormatter={v => `${v}%`} />
                  <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
                    formatter={v => [`${v.toFixed(2)}%`, 'Drawdown']} />
                  <Area type="monotone" dataKey="dd" stroke="#ef4444" fill="#ef4444" fillOpacity={0.3} />
                  <ReferenceLine y={0} stroke="#6b7280" />
                </AreaChart>
              </ResponsiveContainer>
            </Panel>
          )}

          {/* Trade P&L Distribution */}
          {result.trades && result.trades.length > 1 && (
            <Panel title="Trade P&L Distribution">
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={result.trades.map((t, i) => ({ idx: i + 1, pnl: t.pnl_pct }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="idx" tick={{ fontSize: 9, fill: '#9ca3af' }} label={{ value: 'Trade #', position: 'insideBottom', offset: -2, fontSize: 9, fill: '#9ca3af' }} />
                  <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} tickFormatter={v => `${v}%`} />
                  <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
                    formatter={v => [`${v.toFixed(2)}%`, 'P&L']} />
                  <ReferenceLine y={0} stroke="#6b7280" />
                  <Bar dataKey="pnl" fill="#06b6d4"
                    shape={(props) => {
                      const { x, y, width, height, payload } = props
                      const color = payload.pnl >= 0 ? '#10b981' : '#ef4444'
                      return <rect x={x} y={y} width={width} height={height} fill={color} rx={1} />
                    }} />
                </BarChart>
              </ResponsiveContainer>
            </Panel>
          )}

          {/* Regime Performance */}
          {result.performance_by_regime && Object.keys(result.performance_by_regime).length > 0 && (
            <Panel title="Performance by Market Regime">
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={Object.entries(result.performance_by_regime).map(([regime, d]) => ({
                  regime: regime.charAt(0).toUpperCase() + regime.slice(1),
                  avg_pnl: d.avg_pnl, win_rate: d.win_rate, trades: d.trades,
                }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="regime" tick={{ fontSize: 10, fill: '#9ca3af' }} />
                  <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} />
                  <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }} />
                  <Bar dataKey="avg_pnl" fill="#06b6d4" name="Avg P&L %" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="win_rate" fill="#8b5cf6" name="Win Rate %" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Panel>
          )}

          {result.trades && result.trades.length > 0 && (
            <Panel title={`Trade List (${result.trades.length} trades)`}>
              <div className="overflow-x-auto max-h-60 overflow-y-auto">
                <table className="w-full text-[10px]">
                  <thead className="sticky top-0 bg-terminal-panel">
                    <tr className="text-terminal-muted border-b border-terminal-border">
                      <th className="text-left py-1">Entry</th>
                      <th className="text-left">Exit</th>
                      <th className="text-center">Dir</th>
                      <th className="text-right">Entry $</th>
                      <th className="text-right">Exit $</th>
                      <th className="text-right">P&L %</th>
                      <th className="text-left">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.slice(0, 50).map((t, i) => (
                      <tr key={i} className="border-b border-terminal-border/30">
                        <td className="py-0.5">{String(t.entry_date).slice(0, 10)}</td>
                        <td>{String(t.exit_date).slice(0, 10)}</td>
                        <td className={`text-center ${t.direction === 'long' ? 'text-terminal-green' : 'text-terminal-red'}`}>{t.direction}</td>
                        <td className="text-right">${t.entry_price?.toFixed(2)}</td>
                        <td className="text-right">${t.exit_price?.toFixed(2)}</td>
                        <td className={`text-right font-bold ${t.pnl_pct > 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>{t.pnl_pct?.toFixed(1)}%</td>
                        <td>{t.exit_reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </>
      )}

      {result?.error && (
        <Panel><div className="text-terminal-red text-xs">{result.error}</div></Panel>
      )}
    </div>
  )
}
