import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Cell,
} from 'recharts'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function LearningPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const l = analysis.learning || {}

  const driftColor = (drift) => drift ? 'text-terminal-red' : 'text-terminal-green'
  const accColor = (acc) => {
    if (acc == null) return ''
    return acc >= 0.6 ? 'text-terminal-green' : acc >= 0.45 ? 'text-terminal-amber' : 'text-terminal-red'
  }

  return (
    <div className="space-y-4">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Panel><Stat label="Total Predictions" value={l.total_predictions ?? 0} /></Panel>
        <Panel><Stat label="Validated" value={l.validated_count ?? 0} /></Panel>
        <Panel><Stat label="Pending" value={l.pending_count ?? 0} /></Panel>
        <Panel><Stat label="Overall Accuracy"
          value={l.overall_direction_accuracy != null ? `${(l.overall_direction_accuracy * 100).toFixed(1)}%` : '--'}
          color={accColor(l.overall_direction_accuracy)} /></Panel>
      </div>

      {/* Model Performance Table */}
      {l.model_performance && Object.keys(l.model_performance).length > 0 && (
        <Panel title="Model Performance Tracker">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-terminal-muted border-b border-terminal-border">
                  <th className="text-left py-1 px-2">Model</th>
                  <th className="text-right py-1 px-2">Weight</th>
                  <th className="text-right py-1 px-2">MAE</th>
                  <th className="text-right py-1 px-2">RMSE</th>
                  <th className="text-right py-1 px-2">Dir. Accuracy</th>
                  <th className="text-right py-1 px-2">Weight Trend</th>
                  <th className="text-right py-1 px-2">Drift</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(l.model_performance).map(([model, perf]) => (
                  <tr key={model} className="border-b border-terminal-border/30">
                    <td className="py-1 px-2 text-terminal-cyan">{model}</td>
                    <td className="text-right py-1 px-2 font-bold">
                      {perf.current_weight?.toFixed(3) ?? '--'}
                    </td>
                    <td className="text-right py-1 px-2">{perf.mae?.toFixed(4) ?? '--'}</td>
                    <td className="text-right py-1 px-2">{perf.rmse?.toFixed(4) ?? '--'}</td>
                    <td className={`text-right py-1 px-2 ${accColor(perf.direction_accuracy)}`}>
                      {perf.direction_accuracy != null ? `${(perf.direction_accuracy * 100).toFixed(1)}%` : '--'}
                    </td>
                    <td className="text-right py-1 px-2">
                      {perf.weight_trend === 'up' && <span className="text-terminal-green">↑</span>}
                      {perf.weight_trend === 'down' && <span className="text-terminal-red">↓</span>}
                      {perf.weight_trend === 'stable' && <span className="text-terminal-muted">→</span>}
                      {!perf.weight_trend && '--'}
                    </td>
                    <td className={`text-right py-1 px-2 font-bold ${driftColor(perf.drift_detected)}`}>
                      {perf.drift_detected ? 'DRIFT' : 'OK'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {/* Model Weights Chart */}
      {l.model_weights && Object.keys(l.model_weights).length > 0 && (
        <Panel title="Current Model Weights">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={Object.entries(l.model_weights).sort((a, b) => b[1] - a[1]).map(([model, weight]) => ({
              model, weight: weight * 100,
            }))} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis type="number" tick={{ fontSize: 9, fill: '#9ca3af' }} tickFormatter={v => `${v}%`} />
              <YAxis type="category" dataKey="model" tick={{ fontSize: 9, fill: '#9ca3af' }} width={90} />
              <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }}
                formatter={v => [`${v.toFixed(1)}%`, 'Weight']} />
              <Bar dataKey="weight" fill="#06b6d4" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {/* Model Accuracy Comparison */}
      {l.model_performance && Object.keys(l.model_performance).length > 0 && (
        <Panel title="Model Accuracy Comparison">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={Object.entries(l.model_performance).map(([model, perf]) => ({
              model, accuracy: (perf.direction_accuracy || 0) * 100, mae: (perf.mae || 0) * 100,
            }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="model" tick={{ fontSize: 9, fill: '#9ca3af' }} />
              <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} tickFormatter={v => `${v}%`} />
              <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }} />
              <Bar dataKey="accuracy" fill="#10b981" name="Dir. Accuracy %" radius={[3, 3, 0, 0]} />
              <Bar dataKey="mae" fill="#f59e0b" name="MAE %" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {/* Recent Predictions */}
      {l.recent_predictions && l.recent_predictions.length > 0 && (
        <Panel title="Recent Predictions">
          <div className="overflow-x-auto max-h-64 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-terminal-muted border-b border-terminal-border">
                  <th className="text-left py-1 px-2">Model</th>
                  <th className="text-right py-1 px-2">Predicted</th>
                  <th className="text-right py-1 px-2">Actual</th>
                  <th className="text-right py-1 px-2">Error</th>
                  <th className="text-right py-1 px-2">Direction</th>
                  <th className="text-left py-1 px-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {l.recent_predictions.slice(0, 20).map((pred, i) => (
                  <tr key={i} className="border-b border-terminal-border/30">
                    <td className="py-1 px-2 text-terminal-cyan">{pred.model_name}</td>
                    <td className="text-right py-1 px-2">{pred.predicted_value?.toFixed(2) ?? '--'}</td>
                    <td className="text-right py-1 px-2">{pred.actual_value?.toFixed(2) ?? '--'}</td>
                    <td className="text-right py-1 px-2">
                      {pred.error != null ? `${pred.error.toFixed(2)}` : '--'}
                    </td>
                    <td className={`text-right py-1 px-2 ${pred.direction_correct ? 'text-terminal-green' : 'text-terminal-red'}`}>
                      {pred.direction_correct != null ? (pred.direction_correct ? '✓' : '✗') : '--'}
                    </td>
                    <td className="py-1 px-2">
                      <span className={pred.validated ? 'text-terminal-green' : 'text-terminal-amber'}>
                        {pred.validated ? 'Validated' : 'Pending'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {/* Drift Alerts */}
      {l.drift_alerts && l.drift_alerts.length > 0 && (
        <Panel title="Model Drift Alerts">
          <div className="space-y-1">
            {l.drift_alerts.map((alert, i) => (
              <div key={i} className="text-xs p-2 bg-terminal-bg rounded border-l-2 border-terminal-red">
                <span className="text-terminal-red font-bold">DRIFT: </span>
                <span className="text-terminal-text">{alert}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Status Message */}
      {l.total_predictions === 0 && (
        <Panel>
          <div className="text-center text-terminal-muted text-xs p-4">
            Learning loop active. Predictions will appear as the system runs forecasts and validates them over time.
          </div>
        </Panel>
      )}
    </div>
  )
}
