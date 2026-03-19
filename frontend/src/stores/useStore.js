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
}))

export default useStore
