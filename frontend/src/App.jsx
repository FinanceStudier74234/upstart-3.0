import React, { useEffect, Component } from 'react'
import useStore from './stores/useStore'

// Error boundary to prevent full-app crashes from component errors
class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error, info) {
    console.error('Panel error:', error, info.componentStack)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center">
          <div className="text-terminal-red text-sm font-bold mb-2">Component Error</div>
          <div className="text-terminal-muted text-xs mb-4">{this.state.error?.message || 'Unknown error'}</div>
          <button onClick={() => this.setState({ hasError: false, error: null })}
            className="text-xs px-3 py-1 bg-terminal-border text-terminal-text rounded hover:bg-terminal-cyan/20">
            Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
import ExecutiveDashboard from './components/dashboard/ExecutiveDashboard'
import PriceActionPanel from './components/price/PriceActionPanel'
import OptionsPanel from './components/options/OptionsPanel'
import ShortPanel from './components/short/ShortPanel'
import FundingPanel from './components/funding/FundingPanel'
import OriginationPanel from './components/origination/OriginationPanel'
import MacroPanel from './components/macro/MacroPanel'
import ValuationPanel from './components/valuation/ValuationPanel'
import TradeDecisionPanel from './components/trade/TradeDecisionPanel'
import ForecastPanel from './components/forecast/ForecastPanel'
import ScenarioLab from './components/scenario/ScenarioLab'
import QuantPanel from './components/quant/QuantPanel'
import BacktestPanel from './components/backtest/BacktestPanel'
import RiskPanel from './components/risk/RiskPanel'
import CatalystPanel from './components/catalyst/CatalystPanel'
import ReportsPanel from './components/reports/ReportsPanel'
import BotLab from './components/bots/BotLab'
import BehavioralPanel from './components/behavioral/BehavioralPanel'
import NewsPanel from './components/news/NewsPanel'
import ExecutionPanel from './components/execution/ExecutionPanel'
import LearningPanel from './components/learning/LearningPanel'

const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'price', label: 'Price Action' },
  { id: 'options', label: 'Options/Vol' },
  { id: 'short', label: 'Short/Squeeze' },
  { id: 'funding', label: 'Funding' },
  { id: 'origination', label: 'Origination' },
  { id: 'macro', label: 'Macro/Credit' },
  { id: 'valuation', label: 'Valuation' },
  { id: 'trade', label: 'Trade Decision' },
  { id: 'forecast', label: 'Forecast' },
  { id: 'scenario', label: 'Scenario Lab' },
  { id: 'quant', label: 'Quant/PhD Lab' },
  { id: 'catalyst', label: 'Catalysts' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'risk', label: 'Risk/Sizing' },
  { id: 'behavioral', label: 'Behavioral' },
  { id: 'news', label: 'News/Sentiment' },
  { id: 'execution', label: 'Execution' },
  { id: 'learning', label: 'Learning Loop' },
  { id: 'reports', label: 'Reports/Alerts' },
  { id: 'bots', label: 'Bot Lab' },
]

export default function App() {
  const { analysis, activeTab, setActiveTab, fetchAnalysis, loading, error,
          wsConnected, connectWebSocket, disconnectWebSocket } = useStore()

  useEffect(() => {
    fetchAnalysis()
    connectWebSocket()
    const interval = setInterval(fetchAnalysis, 60000)
    return () => {
      clearInterval(interval)
      disconnectWebSocket()
    }
  }, [])

  return (
    <div className="min-h-screen bg-terminal-bg">
      {/* Top Bar */}
      <header className="border-b border-terminal-border px-4 py-2 flex items-center gap-4">
        <div className="text-terminal-cyan font-black text-sm tracking-wider">UPST QUANT HUB</div>
        <div className="text-[10px] text-terminal-muted">v3.0 | Institutional Single-Name Intelligence Platform</div>
        <div className="ml-auto flex items-center gap-2">
          <span className={`text-[10px] ${wsConnected ? 'text-terminal-green' : 'text-terminal-muted'}`}>
            {wsConnected ? '● LIVE' : '○ POLL'}
          </span>
          {loading && <span className="text-terminal-amber text-[10px] animate-pulse">UPDATING...</span>}
          {error && <span className="text-terminal-red text-[10px]">ERR: {error}</span>}
        </div>
      </header>

      {/* Tab Bar — scrollable for all 17 tabs */}
      <nav className="border-b border-terminal-border overflow-x-auto scrollbar-none">
        <div className="flex px-2 gap-0.5 min-w-max">
          {TABS.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`${activeTab === tab.id ? 'tab-active' : 'tab-inactive'} whitespace-nowrap text-[11px] px-2.5 py-1.5`}>
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Content */}
      <main className="p-4 max-w-[1800px] mx-auto">
        <ErrorBoundary key={activeTab}>
          {activeTab === 'dashboard' && <ExecutiveDashboard analysis={analysis} />}
          {activeTab === 'price' && <PriceActionPanel analysis={analysis} />}
          {activeTab === 'options' && <OptionsPanel analysis={analysis} />}
          {activeTab === 'short' && <ShortPanel analysis={analysis} />}
          {activeTab === 'funding' && <FundingPanel analysis={analysis} />}
          {activeTab === 'origination' && <OriginationPanel analysis={analysis} />}
          {activeTab === 'macro' && <MacroPanel analysis={analysis} />}
          {activeTab === 'valuation' && <ValuationPanel analysis={analysis} />}
          {activeTab === 'trade' && <TradeDecisionPanel analysis={analysis} />}
          {activeTab === 'forecast' && <ForecastPanel analysis={analysis} />}
          {activeTab === 'scenario' && <ScenarioLab />}
          {activeTab === 'quant' && <QuantPanel analysis={analysis} />}
          {activeTab === 'catalyst' && <CatalystPanel analysis={analysis} />}
          {activeTab === 'backtest' && <BacktestPanel />}
          {activeTab === 'risk' && <RiskPanel analysis={analysis} />}
          {activeTab === 'behavioral' && <BehavioralPanel analysis={analysis} />}
          {activeTab === 'news' && <NewsPanel analysis={analysis} />}
          {activeTab === 'execution' && <ExecutionPanel analysis={analysis} />}
          {activeTab === 'learning' && <LearningPanel analysis={analysis} />}
          {activeTab === 'reports' && <ReportsPanel analysis={analysis} />}
          {activeTab === 'bots' && <BotLab />}
        </ErrorBoundary>
      </main>

      {/* Footer */}
      <footer className="border-t border-terminal-border px-4 py-2 text-[10px] text-terminal-muted flex justify-between">
        <span>UPST Quant Finance Hub | For Research & Simulation Only | Not Financial Advice</span>
        <span>Data: {analysis?.data_sources ? Object.values(analysis.data_sources).join(', ') : 'N/A'}</span>
      </footer>
    </div>
  )
}
