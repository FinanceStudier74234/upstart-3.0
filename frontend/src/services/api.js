const BASE = '/api/v1'

async function fetchJson(url) {
  const res = await fetch(BASE + url)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function postJson(url, body) {
  const res = await fetch(BASE + url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function fetchBlob(url) {
  const res = await fetch(BASE + url)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.blob()
}

export const api = {
  health: () => fetchJson('/health'),
  fullAnalysis: () => fetchJson('/analysis'),
  quote: (ticker = 'UPST') => fetchJson(`/quote?ticker=${ticker}`),
  bars: (ticker = 'UPST', days = 365) => fetchJson(`/bars?ticker=${ticker}&days=${days}`),
  technical: () => fetchJson('/technical'),
  options: () => fetchJson('/options'),
  short: () => fetchJson('/short'),
  spyRelationship: () => fetchJson('/spy-relationship'),
  scores: () => fetchJson('/scores'),
  tradeDecision: () => fetchJson('/trade-decision'),
  forecast: () => fetchJson('/forecast'),
  risk: () => fetchJson('/risk'),
  valuation: () => fetchJson('/valuation'),
  funding: () => fetchJson('/funding'),
  origination: () => fetchJson('/origination'),
  factor: () => fetchJson('/factor'),
  stress: () => fetchJson('/stress'),
  reflexivity: () => fetchJson('/reflexivity'),
  execution: () => fetchJson('/execution'),
  catalyst: () => fetchJson('/catalyst'),
  probability: () => fetchJson('/probability'),
  overfitting: () => fetchJson('/overfitting'),
  behavioral: () => fetchJson('/behavioral'),
  newsSentiment: () => fetchJson('/news-sentiment'),
  learning: () => fetchJson('/learning'),
  macro: (indicator) => fetchJson(`/macro/${indicator}`),
  news: (limit = 20) => fetchJson(`/news?limit=${limit}`),
  alerts: (severity) => fetchJson(`/alerts${severity ? `?severity=${severity}` : ''}`),
  acknowledgeAlert: (id) => postJson(`/alerts/${id}/acknowledge`, {}),
  dataQuality: () => fetchJson('/data-quality'),
  bots: () => fetchJson('/bots'),
  runBot: (botName, params = {}) => postJson('/bot', { bot_name: botName, params }),
  runScenario: (params) => postJson('/scenario', params),
  runBacktest: (params) => postJson('/backtest', params),
  exportCsv: () => fetchBlob('/export/csv'),
  exportJson: () => fetchBlob('/export/json'),
  exportSummary: () => fetchBlob('/export/summary'),
  schedulerStatus: () => fetchJson('/scheduler/status'),
}
