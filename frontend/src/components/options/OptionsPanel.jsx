import React from 'react'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function OptionsPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const o = analysis.options || {}

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="ATM IV" value={o.atm_iv ? `${(o.atm_iv * 100).toFixed(0)}%` : '--'} /></Panel>
        <Panel><Stat label="IV Rank" value={o.iv_rank != null ? `${(o.iv_rank * 100).toFixed(0)}%` : '--'} /></Panel>
        <Panel><Stat label="IV Percentile" value={o.iv_percentile != null ? `${(o.iv_percentile * 100).toFixed(0)}%` : '--'} /></Panel>
        <Panel><Stat label="IV 30d" value={o.iv_30d ? `${(o.iv_30d * 100).toFixed(0)}%` : '--'} /></Panel>
        <Panel><Stat label="IV Regime" value={o.iv_regime || '--'} /></Panel>
        <Panel><Stat label="P/C Vol Ratio" value={o.put_call_volume_ratio?.toFixed(2)} /></Panel>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="P/C OI Ratio" value={o.put_call_oi_ratio?.toFixed(2)} /></Panel>
        <Panel><Stat label="Realized Vol 30d" value={o.realized_vol_30d ? `${(o.realized_vol_30d * 100).toFixed(0)}%` : '--'} /></Panel>
        <Panel><Stat label="IV-RV Spread" value={o.iv_rv_spread ? `${(o.iv_rv_spread * 100).toFixed(1)}%` : '--'}
          color={o.iv_rv_spread > 0.1 ? 'text-terminal-amber' : ''} /></Panel>
        <Panel><Stat label="Gamma Pivot" value={o.gamma_pivot ? `$${o.gamma_pivot.toFixed(2)}` : '--'} /></Panel>
        <Panel><Stat label="Sentiment" value={o.options_sentiment || '--'} /></Panel>
        <Panel><Stat label="Flow" value={o.premium_flow_direction || '--'} /></Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Expected Move">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">1-Week:</span> {o.expected_move_1w ? `$${o.expected_move_1w.toFixed(2)} (${o.expected_move_pct_1w?.toFixed(1)}%)` : '--'}</div>
            <div><span className="text-terminal-muted">1-Month:</span> {o.expected_move_1m ? `$${o.expected_move_1m.toFixed(2)} (${o.expected_move_pct_1m?.toFixed(1)}%)` : '--'}</div>
            <div><span className="text-terminal-muted">Max Pain:</span> {o.max_pain ? `$${o.max_pain.toFixed(2)}` : '--'}</div>
            <div><span className="text-terminal-muted">Pin Risk:</span>
              <span className={o.pin_risk ? 'text-terminal-amber font-bold' : ''}> {o.pin_risk ? 'YES' : 'NO'}</span>
            </div>
          </div>
        </Panel>

        <Panel title="Options Walls & Greeks">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Call Wall:</span> {o.call_wall ? `$${o.call_wall.toFixed(2)}` : '--'}</div>
            <div><span className="text-terminal-muted">Put Wall:</span> {o.put_wall ? `$${o.put_wall.toFixed(2)}` : '--'}</div>
            <div><span className="text-terminal-muted">Net Delta Exp:</span> {o.net_delta_exposure?.toLocaleString() || '--'}</div>
            <div><span className="text-terminal-muted">Net Gamma Exp:</span> {o.net_gamma_exposure?.toLocaleString() || '--'}</div>
            <div><span className="text-terminal-muted">Total Call OI:</span> {o.total_call_oi?.toLocaleString() || '--'}</div>
            <div><span className="text-terminal-muted">Total Put OI:</span> {o.total_put_oi?.toLocaleString() || '--'}</div>
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Skew & Term Structure">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Put Skew 25d:</span> {o.put_skew_25d?.toFixed(4) || '--'}</div>
            <div><span className="text-terminal-muted">Call Skew 25d:</span> {o.call_skew_25d?.toFixed(4) || '--'}</div>
            <div><span className="text-terminal-muted">Term Structure:</span>
              <span className={`font-bold ${o.term_structure_slope === 'backwardation' ? 'text-terminal-amber' : ''}`}>
                {' '}{o.term_structure_slope || '--'}
              </span>
            </div>
          </div>
        </Panel>

        <Panel title="Volume Summary">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-terminal-muted">Call Volume:</span> {o.total_call_volume?.toLocaleString() || '--'}</div>
            <div><span className="text-terminal-muted">Put Volume:</span> {o.total_put_volume?.toLocaleString() || '--'}</div>
          </div>
        </Panel>
      </div>

      {/* Unusual Activity — calls */}
      {o.unusual_calls && o.unusual_calls.length > 0 && (
        <Panel title="Unusual Call Activity">
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-terminal-muted border-b border-terminal-border">
                  <th className="text-left py-1">Strike</th>
                  <th className="text-right">Expiration</th>
                  <th className="text-right">Volume</th>
                  <th className="text-right">OI</th>
                  <th className="text-right">V/OI</th>
                  <th className="text-right">IV</th>
                </tr>
              </thead>
              <tbody>
                {o.unusual_calls.slice(0, 5).map((a, i) => (
                  <tr key={i} className="border-b border-terminal-border/30">
                    <td className="py-1 text-terminal-green">${a.strike}</td>
                    <td className="text-right">{a.expiration}</td>
                    <td className="text-right">{a.volume?.toLocaleString()}</td>
                    <td className="text-right">{a.open_interest?.toLocaleString()}</td>
                    <td className="text-right font-bold">{a.vol_oi_ratio?.toFixed(1)}x</td>
                    <td className="text-right">{a.iv ? `${(a.iv * 100).toFixed(0)}%` : '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {/* Unusual Activity — puts */}
      {o.unusual_puts && o.unusual_puts.length > 0 && (
        <Panel title="Unusual Put Activity">
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-terminal-muted border-b border-terminal-border">
                  <th className="text-left py-1">Strike</th>
                  <th className="text-right">Expiration</th>
                  <th className="text-right">Volume</th>
                  <th className="text-right">OI</th>
                  <th className="text-right">V/OI</th>
                  <th className="text-right">IV</th>
                </tr>
              </thead>
              <tbody>
                {o.unusual_puts.slice(0, 5).map((a, i) => (
                  <tr key={i} className="border-b border-terminal-border/30">
                    <td className="py-1 text-terminal-red">${a.strike}</td>
                    <td className="text-right">{a.expiration}</td>
                    <td className="text-right">{a.volume?.toLocaleString()}</td>
                    <td className="text-right">{a.open_interest?.toLocaleString()}</td>
                    <td className="text-right font-bold">{a.vol_oi_ratio?.toFixed(1)}x</td>
                    <td className="text-right">{a.iv ? `${(a.iv * 100).toFixed(0)}%` : '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {/* Large Sweeps */}
      {o.large_sweeps && o.large_sweeps.length > 0 && (
        <Panel title="Large Sweeps">
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-terminal-muted border-b border-terminal-border">
                  <th className="text-left py-1">Type</th>
                  <th className="text-right">Strike</th>
                  <th className="text-right">Expiration</th>
                  <th className="text-right">Volume</th>
                  <th className="text-right">Premium $</th>
                </tr>
              </thead>
              <tbody>
                {o.large_sweeps.slice(0, 5).map((s, i) => (
                  <tr key={i} className="border-b border-terminal-border/30">
                    <td className={`py-1 font-bold ${s.type === 'call' ? 'text-terminal-green' : 'text-terminal-red'}`}>{s.type?.toUpperCase()}</td>
                    <td className="text-right">${s.strike}</td>
                    <td className="text-right">{s.expiration}</td>
                    <td className="text-right">{s.volume?.toLocaleString()}</td>
                    <td className="text-right">${s.premium?.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      <ScoreBar label="Options Sentiment" value={o.options_sentiment_score} />
    </div>
  )
}
