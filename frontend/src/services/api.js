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
  macro: (indicator) => fetchJson(`/macro/${indicator}`),
  news: (limit = 20) => fetchJson(`/news?limit=${limit}`),
  alerts: () => fetchJson('/alerts'),
  dataQuality: () => fetchJson('/data-quality'),
  bots: () => fetchJson('/bots'),
  runBot: (botName, params = {}) => postJson('/bot', { bot_name: botName, params }),
  runScenario: (params) => postJson('/scenario', params),
}
