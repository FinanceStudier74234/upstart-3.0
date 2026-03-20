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

  // Actions
  setActiveTab: (tab) => set({ activeTab: tab }),

  fetchAnalysis: async () => {
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
