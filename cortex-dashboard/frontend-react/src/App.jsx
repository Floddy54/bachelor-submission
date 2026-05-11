import { useState, useEffect, lazy, Suspense } from 'react'
// Light tabs — keep eager so the initial tab change is instant
import Overview from './tabs/Overview.jsx'
import TokenScan from './tabs/TokenScan.jsx'
import Statistics from './tabs/Statistics.jsx'
import HpcJobs from './tabs/HpcJobs.jsx'
import Incidents from './tabs/Incidents.jsx'
import Assets from './tabs/Assets.jsx'
import Settings from './tabs/Settings.jsx'
import Activity from './tabs/Activity.jsx'
// Heavy tabs (large JSX trees, 3rd-party charts, etc) — lazy split.
// Vite emits each as its own chunk; user pays the load only when they click in.
const Hunt        = lazy(() => import('./tabs/Hunt.jsx'))
const Experiments = lazy(() => import('./tabs/Experiments.jsx'))
const ThreatIntel = lazy(() => import('./tabs/ThreatIntel.jsx'))
import DemoMode from './components/DemoMode.jsx'
import InvestigationDrawer from './components/InvestigationDrawer.jsx'
import NotificationsBell from './components/NotificationsBell.jsx'
import SearchBar from './components/SearchBar.jsx'
import LiveTicker from './components/LiveTicker.jsx'
import { SkeletonCard, SkeletonKpi } from './components/Skeleton.jsx'
import useEventStream from './hooks/useEventStream.js'
import useUrlState from './hooks/useUrlState.js'
import './App.css'

const TABS = [
  { id: 'overview',     label: 'Overview'     },
  { id: 'incidents',    label: 'Incidents'    },
  { id: 'assets',       label: 'Assets'       },
  { id: 'hunt',         label: 'Hunt'         },
  { id: 'token-scan',   label: 'Token Scan'   },
  { id: 'statistics',   label: 'Statistics'   },
  { id: 'threat-intel', label: 'Threat Intel' },
  { id: 'experiments',  label: 'Experiments'  },
  { id: 'activity',     label: 'Activity'     },
  { id: 'hpc-jobs',     label: 'Jobs'         },
  { id: 'settings',     label: 'Settings'     },
]

const TAB_IDS = new Set(TABS.map(t => t.id))

// Skeleton shown while a lazy-loaded tab's chunk is being fetched
function TabFallback() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <SkeletonCard rows={3} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
        <SkeletonKpi /><SkeletonKpi /><SkeletonKpi /><SkeletonKpi />
      </div>
      <SkeletonCard rows={6} />
    </div>
  )
}

export default function App() {
  // Active tab is mirrored to ?tab=... so the URL is shareable, refresh keeps
  // the user on the same tab, and the back button acts like tab-history.
  const [activeRaw, setActiveUrl] = useUrlState('tab', 'overview')
  const active = TAB_IDS.has(activeRaw) ? activeRaw : 'overview'
  const setActive = setActiveUrl

  const [data, setData]               = useState(null)
  const [loading, setLoading]         = useState(true)
  const [err, setErr]                 = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [demoOpen, setDemoOpen]       = useState(false)
  const [drawerDefense, setDrawerDefense] = useState(null)

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

  // Live event stream — pushes incidents, runs, gate decisions in real time
  const { events: liveEvents, lastEvent, connected: streamConnected } = useEventStream({ bufferSize: 80 })

  // Re-fetch /api/all when a new server event arrives so derived views catch up
  useEffect(() => {
    if (!lastEvent) return
    fetch('/api/all').then(r => r.json()).then(d => {
      setData(d); setLastUpdated(new Date())
    }).catch(() => {})
  }, [lastEvent?.seq])

  const incidents   = data?.incidents?.incidents ?? []
  const allDefenses = data?.asr?.defenses ?? []
  const models      = data?.config?.models ?? []

  function openDefense(def)  { setDrawerDefense(def) }
  function openIncident(inc) { setActive(inc.tab || 'incidents') }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="wordmark">
          <span className="wm-dot" />
          Anti-BAD
          <span className="wm-sub">Defense Console</span>
        </div>
        <nav
          className="tab-nav"
          role="tablist"
          aria-label="Dashboard sections"
          onKeyDown={(e) => {
            // Arrow keys cycle through tabs — standard a11y pattern
            const idx = TABS.findIndex(t => t.id === active)
            if (e.key === 'ArrowRight') {
              e.preventDefault()
              setActive(TABS[(idx + 1) % TABS.length].id)
            } else if (e.key === 'ArrowLeft') {
              e.preventDefault()
              setActive(TABS[(idx - 1 + TABS.length) % TABS.length].id)
            } else if (e.key === 'Home') {
              e.preventDefault()
              setActive(TABS[0].id)
            } else if (e.key === 'End') {
              e.preventDefault()
              setActive(TABS[TABS.length - 1].id)
            }
          }}
        >
          {TABS.map(t => (
            <button
              key={t.id}
              role="tab"
              aria-selected={active === t.id}
              tabIndex={active === t.id ? 0 : -1}
              className={`tab-btn${active === t.id ? ' active' : ''}`}
              onClick={() => setActive(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="topbar-right">
          <SearchBar data={data} onNavigate={setActive} onOpenDefense={openDefense} />
          <LiveTicker event={lastEvent} connected={streamConnected} />
          <NotificationsBell incidents={incidents} onOpenIncident={openIncident} />
          <button className="demo-trigger-btn" onClick={() => { setDemoOpen(true); setActive('overview') }}>
            Demo
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
        <Suspense fallback={<TabFallback />}>
          {active === 'overview'     && <Overview     data={data} loading={loading} onOpenDefense={openDefense} />}
          {active === 'incidents'    && <Incidents    data={data} loading={loading} onNavigate={setActive} />}
          {active === 'assets'       && <Assets       data={data} loading={loading} />}
          {active === 'hunt'         && <Hunt         data={data} loading={loading} />}
          {active === 'token-scan'   && <TokenScan    data={data} loading={loading} />}
          {active === 'statistics'   && <Statistics   data={data} loading={loading} onOpenDefense={openDefense} />}
          {active === 'threat-intel' && <ThreatIntel  data={data} loading={loading} />}
          {active === 'experiments'  && <Experiments  data={data} loading={loading} />}
          {active === 'activity'     && <Activity     data={data} loading={loading} liveEvents={liveEvents} streamConnected={streamConnected} />}
          {active === 'hpc-jobs'     && <HpcJobs      data={data} loading={loading} />}
          {active === 'settings'     && <Settings     data={data} loading={loading} />}
        </Suspense>
      </main>

      <InvestigationDrawer
        defense={drawerDefense}
        onClose={() => setDrawerDefense(null)}
        allDefenses={allDefenses}
        models={models}
      />
    </div>
  )
}
