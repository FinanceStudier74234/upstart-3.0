import { create } from 'zustand'
import { api } from '../services/api'

const useStore = create((set, get) => ({
  // State
  analysis: null,
  loading: false,
  error: null,
  activeTab: 'dashboard',
  scenarioParams: {},
  scenarioResult: null,
  botResult: null,
  backtestResult: null,
  alerts: [],
  lastUpdated: null,
  wsConnected: false,
  _ws: null,

  // Actions
  setActiveTab: (tab) => set({ activeTab: tab }),

  connectWebSocket: () => {
    const { _ws } = get()
    if (_ws && _ws.readyState <= 1) return  // Already connected/connecting

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/v1/ws`
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      set({ wsConnected: true, _ws: ws })
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.event === 'analysis_update' && msg.data) {
          set({ analysis: msg.data, lastUpdated: new Date().toISOString() })
        } else if (msg.event === 'alert' && msg.data) {
          const { alerts } = get()
          set({ alerts: [msg.data, ...alerts].slice(0, 100) })
        } else if (msg.event === 'price_update' && msg.data) {
          const { analysis } = get()
          if (analysis) {
            set({ analysis: { ...analysis, price: msg.data.price } })
          }
        }
      } catch (e) {
        // Ignore malformed messages
      }
    }

    ws.onclose = () => {
      set({ wsConnected: false, _ws: null })
      // Reconnect after 5 seconds
      setTimeout(() => {
        const store = get()
        if (!store.wsConnected) store.connectWebSocket()
      }, 5000)
    }

    ws.onerror = () => {
      set({ wsConnected: false })
    }

    set({ _ws: ws })
  },

  disconnectWebSocket: () => {
    const { _ws } = get()
    if (_ws) {
      _ws.close()
      set({ _ws: null, wsConnected: false })
    }
  },

  fetchAnalysis: async () => {
    const { loading } = get()
    if (loading) return  // Debounce: skip if already loading
    set({ loading: true, error: null })
    try {
      const data = await api.fullAnalysis()
      set({ analysis: data, loading: false, lastUpdated: new Date().toISOString() })
    } catch (e) {
      set({ error: e.message, loading: false })
    }
  },

  runScenario: async (params) => {
    set({ loading: true })
    try {
      const result = await api.runScenario(params)
      set({ scenarioResult: result, scenarioParams: params, loading: false })
    } catch (e) {
      set({ error: e.message, loading: false })
    }
  },

  runBot: async (botName, params) => {
    set({ loading: true })
    try {
      const result = await api.runBot(botName, params)
      set({ botResult: result, loading: false })
    } catch (e) {
      set({ error: e.message, loading: false })
    }
  },

  runBacktest: async (params) => {
    set({ loading: true })
    try {
      const result = await api.runBacktest(params)
      set({ backtestResult: result, loading: false })
    } catch (e) {
      set({ error: e.message, loading: false })
    }
  },

  fetchAlerts: async (severity) => {
    try {
      const result = await api.alerts(severity)
      set({ alerts: result.alerts || [] })
    } catch (e) {
      // silent fail for alerts
    }
  },

  acknowledgeAlert: async (id) => {
    try {
      await api.acknowledgeAlert(id)
      const { alerts } = get()
      set({ alerts: alerts.map(a => a.id === id ? { ...a, acknowledged: true } : a) })
    } catch (e) {
      // silent fail
    }
  },

  exportCsv: async () => {
    try {
      const blob = await api.exportCsv()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'upst_analysis.csv'; a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      set({ error: e.message })
    }
  },

  exportJson: async () => {
    try {
      const blob = await api.exportJson()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'upst_analysis.json'; a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      set({ error: e.message })
    }
  },

  exportSummary: async () => {
    try {
      const blob = await api.exportSummary()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'upst_daily_summary.txt'; a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      set({ error: e.message })
    }
  },
}))

export default useStore
