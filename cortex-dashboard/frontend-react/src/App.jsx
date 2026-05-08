import { useState, useEffect } from 'react'
import Overview from './tabs/Overview.jsx'
import TokenScan from './tabs/TokenScan.jsx'
import Statistics from './tabs/Statistics.jsx'
import HpcJobs from './tabs/HpcJobs.jsx'
import DemoMode from './components/DemoMode.jsx'
import './App.css'

const TABS = [
  { id: 'overview',   label: 'Overview'   },
  { id: 'token-scan', label: 'Token Scan' },
  { id: 'statistics', label: 'Statistics' },
  { id: 'hpc-jobs',   label: 'HPC Jobs'   },
]

export default function App() {
  const [active, setActive] = useState('overview')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [demoOpen, setDemoOpen] = useState(false)

  useEffect(() => {
    let alive = true
    const load = () => {
      fetch('/api/all')
        .then(r => r.json())
        .then(d => {
          if (alive) {
            setData(d)
            setLoading(false)
            setLastUpdated(new Date())
          }
        })
        .catch(e => { if (alive) { setErr(e.message); setLoading(false) } })
    }
    load()
    const t = setInterval(load, 30000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  return (
    <div className="shell">
      <header className="topbar">
        <div className="wordmark">
          <span className="wm-dot" />
          Anti-BAD
          <span className="wm-sub">Defense Console</span>
        </div>
        <nav className="tab-nav">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`tab-btn${active === t.id ? ' active' : ''}`}
              onClick={() => setActive(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="topbar-right">
          <span className={`live-dot ${loading ? 'pulsing' : err ? 'err' : 'ok'}`} />
          <span className="live-label">{loading ? 'loading' : err ? 'offline' : 'live'}</span>
          {lastUpdated && !loading && !err && (
            <span className="last-updated">
              Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              {' · '}30s
            </span>
          )}
          <button className="demo-trigger-btn" onClick={() => { setDemoOpen(true); setActive('overview') }}>
            ▶ Demo
          </button>
        </div>
      </header>

      {demoOpen && (
        <DemoMode
          onNavigate={tab => setActive(tab)}
          onClose={() => setDemoOpen(false)}
        />
      )}

      <main className="content">
        {active === 'overview'   && <Overview   data={data} loading={loading} />}
        {active === 'token-scan' && <TokenScan  data={data} loading={loading} />}
        {active === 'statistics' && <Statistics data={data} loading={loading} />}
        {active === 'hpc-jobs'   && <HpcJobs    data={data} loading={loading} />}
      </main>
    </div>
  )
}
