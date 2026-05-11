import { useState, useEffect, useMemo } from 'react'
import useUrlState, { useDebounce } from '../hooks/useUrlState.js'
import './Activity.css'


const STATUS_COLOR = {
  OK:        'var(--ok)',
  FAILED:    'var(--danger)',
  HIGH:      'var(--danger)',
  MEDIUM:    'var(--warn)',
  LOW:       'var(--ok)',
  RUNNING:   'var(--teal)',
  COMPLETED: 'var(--ok)',
  PENDING:   'var(--warn)',
  QUEUED:    'var(--warn)',
}

const INT_STATUS_COLOR = {
  OK:       'var(--ok)',
  OFFLINE:  'var(--danger)',
  MISSING:  'var(--warn)',
  DISABLED: 'var(--ink-3)',
  FALLBACK: 'var(--warn)',
}

const KIND_TAG = {
  run:      'RUN',
  incident: 'INC',
  job:      'JOB',
}

function EventRow({ e }) {
  const color = STATUS_COLOR[e.status] || 'var(--ink-3)'
  return (
    <div className="act-row">
      <span className="act-kind" style={{ color, borderColor: color }}>{KIND_TAG[e.kind] || 'EVT'}</span>
      <div className="act-body">
        <div className="act-title">{e.title}</div>
        <div className="act-sub">{e.subtitle}</div>
      </div>
      <div className="act-meta">
        <span className="act-status" style={{ color }}>{e.status}</span>
        <span className="act-actor">{e.actor}</span>
      </div>
    </div>
  )
}

function TrendChart({ runs }) {
  const buckets = useMemo(() => {
    const byDef = {}
    for (const r of runs.slice(0, 50).reverse()) {
      if (!r.ok || !r.defense) continue
      if (!byDef[r.defense]) byDef[r.defense] = []
      byDef[r.defense].push({ ts: r.ts, defense: r.defense })
    }
    return byDef
  }, [runs])

  const defenses = Object.keys(buckets)
  if (defenses.length === 0) {
    return (
      <div className="act-trend-empty">
        No completed runs yet. Trends appear here once you launch defenses via the Experiments tab.
      </div>
    )
  }

  // Simple bar: count per defense
  const max = Math.max(...defenses.map(d => buckets[d].length), 1)
  return (
    <div className="act-trend">
      {defenses.map(d => (
        <div key={d} className="act-trend-row">
          <span className="act-trend-name">{d}</span>
          <div className="act-trend-bar-track">
            <div className="act-trend-bar-fill" style={{ width: `${(buckets[d].length / max) * 100}%` }} />
          </div>
          <span className="num act-trend-count">{buckets[d].length}</span>
        </div>
      ))}
    </div>
  )
}

function IntegrationCard({ i }) {
  const color = INT_STATUS_COLOR[i.status] || 'var(--ink-3)'
  return (
    <div className="int-card" style={{ borderLeft: `3px solid ${color}` }}>
      <div className="int-head">
        <span className="int-name">{i.name}</span>
        <span className="int-status" style={{ color, borderColor: color + '55' }}>{i.status}</span>
      </div>
      <div className="int-detail num">{i.detail || '—'}</div>
      <div className="int-note">{i.note}</div>
    </div>
  )
}

function downloadCsv(filename, rows) {
  if (!rows.length) return
  const keys = Object.keys(rows[0])
  const escape = v => `"${String(v ?? '').replace(/"/g, '""')}"`
  const csv = [keys.join(','), ...rows.map(r => keys.map(k => escape(r[k])).join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

function liveToEvent(e) {
  // Convert SSE-bus event into the EventRow shape used below
  const p = e.payload || {}
  if (e.kind === 'run') {
    return {
      kind: 'run', ts: e.ts,
      title:    `${p.defense || 'run'} on ${p.model || '?'}`,
      subtitle: `compute=${p.compute || '?'} seed=${p.seed ?? '?'}`,
      status:   p.ok ? 'OK' : 'FAILED',
      actor:    p.actor || 'unknown',
    }
  }
  if (e.kind === 'incident') {
    return {
      kind: 'incident', ts: e.ts,
      title:    p.title || 'New incident',
      subtitle: `${p.severity || ''} ${p.category || ''}`,
      status:   p.severity || 'MED',
      actor:    'system',
    }
  }
  if (e.kind === 'gate') {
    return {
      kind: 'run', ts: e.ts,
      title:    `gate batch ${p.n_total} rows`,
      subtitle: `drop ${p.counts?.DROP || 0}  san ${p.counts?.SANITIZE || 0}  allow ${p.counts?.ALLOW || 0}`,
      status:   'OK',
      actor:    p.actor || 'system',
    }
  }
  return null
}

export default function Activity({ data, loading, liveEvents = [], streamConnected = false }) {
  const [polledEvents, setPolledEvents] = useState([])
  const [runs,         setRuns]         = useState([])
  const [integrations, setIntegrations] = useState([])

  useEffect(() => {
    setPolledEvents(data?.activity?.events ?? [])
    setRuns(data?.runs?.runs ?? [])
    setIntegrations(data?.integrations?.integrations ?? [])
  }, [data])

  const [filterKind, setFilterKind] = useUrlState('act_kind', 'ALL')
  const [filterText, setFilterText] = useUrlState('act_q', '')
  const debouncedText = useDebounce(filterText, 250)

  // Merge live + polled, dedupe by ts+title, then apply filters
  const events = useMemo(() => {
    const live = liveEvents.map(liveToEvent).filter(Boolean)
    const seen = new Set()
    const all  = [...live, ...polledEvents]
    const merged = all.filter(e => {
      const key = `${e.ts}|${e.title}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    }).sort((a, b) => (b.ts || '').localeCompare(a.ts || ''))

    const t = (debouncedText || '').toLowerCase()
    return merged.filter(e => {
      if (filterKind !== 'ALL' && e.kind !== filterKind.toLowerCase()) return false
      if (t) {
        const hay = `${e.title} ${e.subtitle} ${e.actor}`.toLowerCase()
        if (!hay.includes(t)) return false
      }
      return true
    })
  }, [liveEvents, polledEvents, filterKind, debouncedText])

  return (
    <div className="activity">
      <div className="card act-intro">
        <div className="section-title">Activity · Run History · Integration Health</div>
        <p className="act-desc">
          Live event stream combining experiment runs, auto-derived incidents, and compute-job state.
          Persistent run history is kept in <code>data/runs_history.json</code> across server restarts.
          Integration health reflects every external system the dashboard connects to.
        </p>
      </div>

      {/* Integration Health */}
      <div className="card">
        <div className="section-title">Integration Health</div>
        <div className="int-grid">
          {integrations.map(i => <IntegrationCard key={i.id} i={i} />)}
        </div>
      </div>

      <div className="act-grid">
        {/* Live event feed */}
        <div className="card act-feed-card">
          <div className="act-feed-head">
            <div className="section-title">Live Event Feed</div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <span style={{
                fontSize: 10, padding: '2px 8px', borderRadius: 10,
                border: '1px solid', fontFamily: 'var(--mono)',
                color: streamConnected ? 'var(--ok)' : 'var(--ink-3)',
                borderColor: streamConnected ? 'var(--ok)' : 'var(--ink-3)',
              }}>
                {streamConnected ? 'SSE LIVE' : 'POLLING'}
              </span>
              <span className="act-feed-count num">{events.length} events</span>
            </div>
          </div>
          <div className="act-filter-row">
            {['ALL', 'RUN', 'INCIDENT', 'JOB'].map(k => (
              <button
                key={k}
                className={`act-filter-chip ${filterKind === k ? 'active' : ''}`}
                onClick={() => setFilterKind(k)}
              >
                {k.charAt(0) + k.slice(1).toLowerCase()}
              </button>
            ))}
            <input
              className="act-filter-input"
              placeholder="Filter events..."
              value={filterText}
              onChange={e => setFilterText(e.target.value)}
            />
          </div>
          {loading && <div className="loading-state">Polling…</div>}
          {events.length === 0 && !loading && (
            <div className="act-trend-empty">
              {filterKind !== 'ALL' || debouncedText
                ? 'No events match the current filter.'
                : 'No recent activity. Run a defense via the Experiments tab.'}
            </div>
          )}
          <div className="act-feed-list">
            {events.map((e, i) => <EventRow key={i} e={e} />)}
          </div>
        </div>

        {/* Run history + trend */}
        <div className="act-right">
          <div className="card">
            <div className="act-feed-head">
              <div className="section-title">Run Distribution by Defense</div>
              <span className="num">{runs.length} runs</span>
            </div>
            <TrendChart runs={runs} />
          </div>

          <div className="card">
            <div className="act-feed-head">
              <div className="section-title">Recent Runs</div>
              <button className="act-export-btn" disabled={runs.length === 0}
                onClick={() => downloadCsv('runs_history.csv', runs.map(r => ({
                  ts: r.ts, actor: r.actor, defense: r.defense, model: r.model,
                  compute: r.compute, ok: r.ok, job_id: r.job_id || '',
                })))}>
                Export CSV
              </button>
            </div>
            <table className="runs-table">
              <thead>
                <tr><th>Time</th><th>Actor</th><th>Defense</th><th>Model</th><th>Compute</th><th>Status</th></tr>
              </thead>
              <tbody>
                {runs.slice(0, 12).map((r, i) => (
                  <tr key={i}>
                    <td className="num runs-time">{r.ts ? new Date(r.ts).toLocaleTimeString() : '—'}</td>
                    <td>{r.actor || '—'}</td>
                    <td>{r.defense || '—'}</td>
                    <td className="num">{r.model || '—'}</td>
                    <td>
                      <span className="pill" style={{ color: r.compute === 'local' ? 'var(--teal)' : '#C084FC' }}>
                        {r.compute || '—'}
                      </span>
                    </td>
                    <td>
                      <span className="pill" style={{ color: r.ok ? 'var(--ok)' : 'var(--danger)' }}>
                        {r.ok ? 'OK' : 'FAIL'}
                      </span>
                    </td>
                  </tr>
                ))}
                {runs.length === 0 && (
                  <tr><td colSpan={6} className="runs-empty">No runs logged yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
