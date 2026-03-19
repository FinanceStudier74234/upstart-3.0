import React, { useState } from 'react'
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
