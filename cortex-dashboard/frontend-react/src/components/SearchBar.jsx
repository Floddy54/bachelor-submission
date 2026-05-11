import { useState, useEffect, useRef } from 'react'
import './SearchBar.css'

/**
 * Cortex-style command-K bar. Parses `key:value AND/OR key:value` and
 * routes the user to the right tab with filter applied.
 *
 * Supported keys are derived from /api/config so a teammate adding a new
 * dataset / defense / model gets autocomplete automatically.
 */

function parseQuery(q) {
  const tokens = q.split(/\s+/).filter(Boolean)
  const filters = {}
  const free = []
  for (const t of tokens) {
    const m = t.match(/^([a-z_]+):(.+)$/i)
    if (m) {
      const k = m[1].toLowerCase()
      let v = m[2]
      // Strip quotes if present
      v = v.replace(/^["']|["']$/g, '')
      filters[k] = v
    } else if (t.toUpperCase() !== 'AND' && t.toUpperCase() !== 'OR') {
      free.push(t)
    }
  }
  return { filters, free }
}

export default function SearchBar({ data, onNavigate, onOpenDefense }) {
  const [open,  setOpen]  = useState(false)
  const [q,     setQ]     = useState('')
  const inputRef = useRef(null)
  const ref = useRef(null)

  useEffect(() => {
    function onKey(e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(true)
        setTimeout(() => inputRef.current?.focus(), 50)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    function clickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', clickOutside)
    return () => document.removeEventListener('mousedown', clickOutside)
  }, [])

  // Build results
  const { filters, free } = parseQuery(q)
  const freeStr = free.join(' ').toLowerCase()
  const results = []

  if (q.trim().length > 0) {
    // Defenses
    const defenses = data?.asr?.defenses ?? []
    for (const d of defenses) {
      const name = (d.name || '').toLowerCase()
      const fam  = (d.family || '').toLowerCase()
      let match = true
      if (filters.defense && !name.includes(filters.defense.toLowerCase())) match = false
      if (filters.family  && !fam.includes(filters.family.toLowerCase()))  match = false
      if (filters.verdict && d.verdict !== filters.verdict.toUpperCase())  match = false
      if (filters.asr_gt  && !(d.asr > parseFloat(filters.asr_gt)))         match = false
      if (filters.asr_lt  && !(d.asr < parseFloat(filters.asr_lt)))         match = false
      if (freeStr && !name.includes(freeStr) && !fam.includes(freeStr))     match = false
      if (match) results.push({ kind: 'defense', tab: 'overview', item: d, label: d.name, sub: `${d.family} · ${d.asr.toFixed(2)}% ASR · ${d.verdict}` })
    }

    // Models
    const models = data?.assets?.assets ?? []
    for (const m of models) {
      const id = (m.id || '').toLowerCase()
      let match = true
      if (filters.model && !id.includes(filters.model.toLowerCase())) match = false
      if (filters.risk  && m.risk_level !== filters.risk.toUpperCase()) match = false
      if (freeStr && !id.includes(freeStr)) match = false
      if (match) results.push({ kind: 'asset', tab: 'assets', item: m, label: m.id, sub: `risk ${m.risk_score}/100 · ${m.risk_level} · ${m.residual_asr.toFixed(2)}% ASR` })
    }

    // Incidents
    const incs = data?.incidents?.incidents ?? []
    for (const i of incs) {
      const t = (i.title || '').toLowerCase()
      let match = true
      if (filters.severity && i.severity !== filters.severity.toUpperCase()) match = false
      if (freeStr && !t.includes(freeStr) && !i.category.toLowerCase().includes(freeStr)) match = false
      if (match) results.push({ kind: 'incident', tab: i.tab || 'incidents', item: i, label: i.title, sub: `${i.severity} · ${i.category}` })
    }

    // Jobs
    const jobs = data?.jobs?.jobs ?? []
    for (const j of jobs) {
      const id = (j.job_id || '').toLowerCase()
      const def = (j.defense || j.name || '').toLowerCase()
      let match = true
      if (filters.status && (j.state || j.status) !== filters.status.toUpperCase()) match = false
      if (filters.job_id && !id.includes(filters.job_id.toLowerCase())) match = false
      if (freeStr && !id.includes(freeStr) && !def.includes(freeStr)) match = false
      if (match) results.push({ kind: 'job', tab: 'hpc-jobs', item: j, label: j.job_id, sub: `${j.defense || j.name} · ${j.state || j.status}` })
    }
  }

  function activate(r) {
    setOpen(false)
    setQ('')
    if (r.kind === 'defense') {
      onOpenDefense?.(r.item)
    } else {
      onNavigate?.(r.tab)
    }
  }

  const cfg = data?.config
  const helpRows = cfg ? [
    `defense:${(data?.asr?.defenses?.[0]?.name || 'WAG').toLowerCase().split(' ')[0]}`,
    'verdict:STRONG',
    `model:${cfg.models?.[0] || 'model1'}`,
    'risk:HIGH',
    'severity:HIGH',
    'asr_gt:30',
    'status:RUNNING',
  ] : []

  return (
    <div className="sb-wrap" ref={ref}>
      <button className="sb-trigger" onClick={() => { setOpen(true); setTimeout(() => inputRef.current?.focus(), 50) }}>
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.4">
          <circle cx="7" cy="7" r="5" />
          <line x1="11" y1="11" x2="14" y2="14" />
        </svg>
        <span className="sb-trigger-label">Search · defenses, models, incidents</span>
        <kbd className="sb-kbd">⌘K</kbd>
      </button>

      {open && (
        <div className="sb-modal-backdrop" onClick={() => setOpen(false)}>
          <div className="sb-modal" onClick={e => e.stopPropagation()}>
            <div className="sb-modal-head">
              <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.4">
                <circle cx="7" cy="7" r="5" />
                <line x1="11" y1="11" x2="14" y2="14" />
              </svg>
              <input
                ref={inputRef}
                className="sb-input"
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="e.g. defense:WAG, severity:HIGH, model:model2, asr_gt:30"
                onKeyDown={e => {
                  if (e.key === 'Enter' && results[0]) activate(results[0])
                  if (e.key === 'Escape') setOpen(false)
                }}
                autoFocus
              />
              <kbd className="sb-kbd">esc</kbd>
            </div>

            {q.trim().length === 0 ? (
              <div className="sb-help">
                <div className="sb-help-title">XQL-style filter syntax</div>
                <div className="sb-help-rows">
                  {helpRows.map(h => (
                    <button key={h} className="sb-help-chip" onClick={() => setQ(h)}>{h}</button>
                  ))}
                </div>
                <div className="sb-help-hint">
                  Keys: <code>defense</code> · <code>verdict</code> · <code>family</code> · <code>model</code> · <code>risk</code> · <code>severity</code> · <code>asr_gt</code> · <code>asr_lt</code> · <code>status</code> · <code>job_id</code>
                </div>
              </div>
            ) : results.length === 0 ? (
              <div className="sb-empty">No matches for <code>{q}</code></div>
            ) : (
              <div className="sb-results">
                {results.slice(0, 12).map((r, i) => (
                  <button key={i} className={`sb-result sb-result-${r.kind}`} onClick={() => activate(r)}>
                    <span className="sb-result-kind">{r.kind}</span>
                    <span className="sb-result-label">{r.label}</span>
                    <span className="sb-result-sub">{r.sub}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
