import { useState, useMemo } from 'react'
import useUrlState from '../hooks/useUrlState.js'
import { downloadCsv } from '../hooks/useCsvExport.js'
import './Incidents.css'

const SEV_META = {
  HIGH:   { color: 'var(--danger)', bg: 'rgba(255, 90, 95, 0.10)',  tag: 'HIGH', order: 0 },
  MEDIUM: { color: 'var(--warn)',   bg: 'rgba(245, 181, 68, 0.10)', tag: 'MED',  order: 1 },
  LOW:    { color: 'var(--ok)',     bg: 'rgba(34, 197, 94, 0.10)',  tag: 'LOW',  order: 2 },
}

const CATEGORY_TAGS = {
  'Defense Failure':          'DEF',
  'Statistical Significance': 'STAT',
  'Cross-Model Variance':     'VAR',
  'Compute Pipeline':         'COMP',
  'Threat Intelligence':      'TI',
}

export default function Incidents({ data, loading, onNavigate }) {
  const inc = data?.incidents
  const items = inc?.incidents ?? []
  // Severity filter persisted in URL so links like ?tab=incidents&sev=HIGH work
  const [filterSev, setFilterSev] = useUrlState('sev', 'ALL')
  const [expanded,  setExpanded]  = useState(new Set())

  const filtered = useMemo(() => {
    if (filterSev === 'ALL') return items
    return items.filter(i => i.severity === filterSev)
  }, [items, filterSev])

  function toggle(id) {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const counts = inc?.by_severity || { HIGH: 0, MEDIUM: 0, LOW: 0 }

  return (
    <div className="incidents">
      <div className="card inc-intro">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
          <div style={{ flex: 1 }}>
            <div className="section-title">Incidents · Auto-derived from Defense Telemetry</div>
            <p className="inc-desc">
              Live findings derived from defense ASR, statistical significance, per-model variance, and compute-job status.
              Click any incident to expand for evidence, impact and recommendation. Click the linked tab to drill into source data.
            </p>
          </div>
          <button
            className="inc-export-btn"
            disabled={items.length === 0}
            onClick={() => downloadCsv(
              `incidents_${Date.now()}.csv`,
              items.map(i => ({
                id: i.id, severity: i.severity, category: i.category,
                title: i.title, evidence: i.evidence, impact: i.impact,
                recommendation: i.recommendation,
                affected: (i.affected || []).join('|'),
                timestamp: i.timestamp, status: i.status,
              }))
            )}>
            Export CSV
          </button>
        </div>
      </div>

      {/* Severity counters */}
      <div className="inc-counters">
        <button className={`inc-counter ${filterSev === 'ALL' ? 'active' : ''}`} onClick={() => setFilterSev('ALL')}>
          <span className="inc-counter-label">All</span>
          <span className="inc-counter-num num">{items.length}</span>
        </button>
        <button className={`inc-counter sev-high ${filterSev === 'HIGH' ? 'active' : ''}`} onClick={() => setFilterSev('HIGH')}>
          <span className="inc-counter-label">High</span>
          <span className="inc-counter-num num">{counts.HIGH}</span>
        </button>
        <button className={`inc-counter sev-medium ${filterSev === 'MEDIUM' ? 'active' : ''}`} onClick={() => setFilterSev('MEDIUM')}>
          <span className="inc-counter-label">Medium</span>
          <span className="inc-counter-num num">{counts.MEDIUM}</span>
        </button>
        <button className={`inc-counter sev-low ${filterSev === 'LOW' ? 'active' : ''}`} onClick={() => setFilterSev('LOW')}>
          <span className="inc-counter-label">Low</span>
          <span className="inc-counter-num num">{counts.LOW}</span>
        </button>
      </div>

      {loading && <div className="loading-state">Loading incidents…</div>}

      {!loading && filtered.length === 0 && (
        <div className="card inc-empty">
          <div className="inc-empty-icon">OK</div>
          <div className="inc-empty-title">No open incidents</div>
          <div className="inc-empty-desc">
            All defenses meet thresholds: ASR &lt; 30%, Cohen's h ≥ 0.8, per-model variance &lt; 25 pp,
            no SLURM failures.
          </div>
        </div>
      )}

      <div className="inc-list">
        {filtered.map(i => {
          const meta = SEV_META[i.severity] || SEV_META.LOW
          const open = expanded.has(i.id)
          return (
            <div key={i.id} className={`inc-card ${open ? 'open' : ''}`} style={{ borderLeftColor: meta.color }}>
              <button className="inc-head" onClick={() => toggle(i.id)}>
                <span className="inc-sev-block" style={{ background: meta.bg, color: meta.color, borderColor: meta.color + '44' }}>
                  <span className="inc-sev-label">{i.severity}</span>
                </span>
                <span className="inc-id">{i.id}</span>
                <span className="inc-category">
                  <span className="inc-cat-icon">{CATEGORY_TAGS[i.category] || 'EVT'}</span>
                  {i.category}
                </span>
                <span className="inc-title">{i.title}</span>
                <span className="inc-chevron">{open ? '▾' : '▸'}</span>
              </button>

              {open && (
                <div className="inc-body">
                  <div className="inc-row">
                    <span className="inc-key">Evidence</span>
                    <span className="inc-val">{i.evidence}</span>
                  </div>
                  <div className="inc-row">
                    <span className="inc-key">Impact</span>
                    <span className="inc-val">{i.impact}</span>
                  </div>
                  <div className="inc-row inc-rec">
                    <span className="inc-key">Recommendation</span>
                    <span className="inc-val">{i.recommendation}</span>
                  </div>
                  <div className="inc-row inc-affected">
                    <span className="inc-key">Affected</span>
                    <span className="inc-val">
                      {i.affected.map(a => <code key={a} className="inc-affected-chip">{a}</code>)}
                    </span>
                  </div>
                  <div className="inc-foot">
                    <span className="inc-status num">STATUS: {i.status}</span>
                    {i.tab && (
                      <button className="inc-drill-btn" onClick={() => onNavigate?.(i.tab)}>
                        Open {i.tab}
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
