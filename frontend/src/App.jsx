import React, { useEffect } from 'react'
import useStore from './stores/useStore'
import ExecutiveDashboard from './components/dashboard/ExecutiveDashboard'
import ScenarioLab from './components/scenario/ScenarioLab'
import BotLab from './components/bots/BotLab'

const TABS = [
  { id: 'dashboard', label: 'Executive Dashboard' },
  { id: 'scenario', label: 'Scenario Lab' },
  { id: 'bots', label: 'Bot / Simulation Lab' },
]

export default function App() {
  const { analysis, activeTab, setActiveTab, fetchAnalysis, loading, error } = useStore()

  useEffect(() => {
    fetchAnalysis()
    // Auto-refresh every 60s
    const interval = setInterval(fetchAnalysis, 60000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-terminal-bg">
      {/* Top Bar */}
      <header className="border-b border-terminal-border px-4 py-2 flex items-center gap-4">
        <div className="text-terminal-cyan font-black text-sm tracking-wider">UPST QUANT HUB</div>
        <div className="text-[10px] text-terminal-muted">v3.0 | Institutional Single-Name Intelligence Platform</div>
        <div className="ml-auto flex items-center gap-2">
          {loading && <span className="text-terminal-amber text-[10px] animate-pulse">UPDATING...</span>}
          {error && <span className="text-terminal-red text-[10px]">ERR: {error}</span>}
        </div>
      </header>

      {/* Tab Bar */}
      <nav className="border-b border-terminal-border flex px-4 gap-1">
        {TABS.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={activeTab === tab.id ? 'tab-active' : 'tab-inactive'}>
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Content */}
      <main className="p-4 max-w-[1800px] mx-auto">
        {activeTab === 'dashboard' && <ExecutiveDashboard analysis={analysis} />}
        {activeTab === 'scenario' && <ScenarioLab />}
        {activeTab === 'bots' && <BotLab />}
      </main>

      {/* Footer */}
      <footer className="border-t border-terminal-border px-4 py-2 text-[10px] text-terminal-muted flex justify-between">
        <span>UPST Quant Finance Hub | For Research & Simulation Only | Not Financial Advice</span>
        <span>Data: {analysis?.data_sources ? Object.values(analysis.data_sources).join(', ') : 'N/A'}</span>
      </footer>
    </div>
  )
}
