import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import Panel from '../common/Panel'
import Stat from '../common/Stat'
import ScoreBar from '../common/ScoreBar'

export default function NewsPanel({ analysis }) {
  if (!analysis) return <div className="text-terminal-muted p-4">Loading...</div>
  const n = analysis.news || {}

  const sentColor = (val) => {
    if (val == null) return ''
    return val > 0.2 ? 'text-terminal-green' : val < -0.2 ? 'text-terminal-red' : 'text-terminal-amber'
  }

  const catColor = (cat) => {
    const bearish = ['regulatory', 'credit', 'world']
    const bullish = ['funding', 'origination', 'fintech']
    if (bearish.includes(cat)) return 'text-terminal-red'
    if (bullish.includes(cat)) return 'text-terminal-green'
    return 'text-terminal-cyan'
  }

  return (
    <div className="space-y-4">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Panel><Stat label="Avg Sentiment" value={n.avg_sentiment?.toFixed(2)}
          color={sentColor(n.avg_sentiment)} /></Panel>
        <Panel><Stat label="Sentiment Trend" value={n.sentiment_trend || '--'}
          color={n.sentiment_trend === 'improving' ? 'text-terminal-green' :
                 n.sentiment_trend === 'deteriorating' ? 'text-terminal-red' : ''} /></Panel>
        <Panel><Stat label="News Volume" value={n.news_volume} /></Panel>
        <Panel><Stat label="High Impact" value={n.high_impact_count}
          color={n.high_impact_count > 3 ? 'text-terminal-amber' : ''} /></Panel>
        <Panel><Stat label="Policy Risk" value={n.risk_flags?.policy_risk ? 'YES' : 'No'}
          color={n.risk_flags?.policy_risk ? 'text-terminal-red' : 'text-terminal-green'} /></Panel>
        <Panel><Stat label="World Risk" value={n.risk_flags?.world_risk ? 'YES' : 'No'}
          color={n.risk_flags?.world_risk ? 'text-terminal-red' : 'text-terminal-green'} /></Panel>
      </div>

      {/* Category Breakdown */}
      {n.category_breakdown && Object.keys(n.category_breakdown).length > 0 && (
        <Panel title="Category Breakdown">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            {Object.entries(n.category_breakdown).map(([cat, count]) => (
              <div key={cat} className="p-2 bg-terminal-bg rounded flex justify-between">
                <span className={catColor(cat)}>{cat}</span>
                <span className="text-terminal-text font-bold">{count}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Category Distribution Chart */}
      {n.category_breakdown && Object.keys(n.category_breakdown).length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Panel title="Category Distribution">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={Object.entries(n.category_breakdown).map(([cat, count]) => ({ cat, count }))} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis type="number" tick={{ fontSize: 9, fill: '#9ca3af' }} />
                <YAxis type="category" dataKey="cat" tick={{ fontSize: 9, fill: '#9ca3af' }} width={80} />
                <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }} />
                <Bar dataKey="count" fill="#06b6d4" name="Articles" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Panel>
          <Panel title="Sentiment Composition">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={(() => {
                  const articles = n.articles || []
                  const pos = articles.filter(a => (a.sentiment_score || 0) > 0.2).length
                  const neg = articles.filter(a => (a.sentiment_score || 0) < -0.2).length
                  const neu = articles.length - pos - neg
                  return [
                    { name: 'Positive', value: pos },
                    { name: 'Neutral', value: neu },
                    { name: 'Negative', value: neg },
                  ].filter(d => d.value > 0)
                })()} cx="50%" cy="50%" innerRadius={40} outerRadius={70} paddingAngle={3} dataKey="value">
                  <Cell fill="#10b981" />
                  <Cell fill="#6b7280" />
                  <Cell fill="#ef4444" />
                </Pie>
                <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 11 }} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
              </PieChart>
            </ResponsiveContainer>
          </Panel>
        </div>
      )}

      {/* News Articles */}
      {n.articles && n.articles.length > 0 && (
        <Panel title="Recent Headlines">
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {n.articles.slice(0, 20).map((article, i) => (
              <div key={i} className="p-2 bg-terminal-bg rounded text-xs border-l-2"
                style={{ borderColor: article.sentiment_score > 0.2 ? '#10b981' :
                                     article.sentiment_score < -0.2 ? '#ef4444' : '#6b7280' }}>
                <div className="flex justify-between mb-1">
                  <span className="text-terminal-text font-medium">{article.headline}</span>
                  <span className={`ml-2 shrink-0 ${sentColor(article.sentiment_score)}`}>
                    {article.sentiment_score?.toFixed(2)}
                  </span>
                </div>
                <div className="flex gap-3 text-terminal-muted">
                  <span>{article.source_name || 'Unknown'}</span>
                  <span className={catColor(article.category)}>{article.category}</span>
                  {article.relevance_score && (
                    <span>Relevance: {(article.relevance_score * 100).toFixed(0)}%</span>
                  )}
                  {article.published_at && (
                    <span>{new Date(article.published_at).toLocaleDateString()}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Risk Flags */}
      {n.risk_flags && (
        <Panel title="Risk Flags">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            {Object.entries(n.risk_flags).map(([flag, active]) => (
              <div key={flag} className="p-2 bg-terminal-bg rounded flex justify-between">
                <span className="text-terminal-muted">{flag.replace(/_/g, ' ')}</span>
                <span className={active ? 'text-terminal-red font-bold' : 'text-terminal-green'}>
                  {active ? 'ACTIVE' : 'Clear'}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <ScoreBar label="News Sentiment Score" value={n.sentiment_score} />
    </div>
  )
}
