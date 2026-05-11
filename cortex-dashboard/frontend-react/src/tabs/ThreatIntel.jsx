import { useState, useEffect, useMemo } from 'react'
import useUrlState from '../hooks/useUrlState.js'
import './ThreatIntel.css'

const RELEVANCE_META = {
  PRIMARY:    { color: 'var(--danger)', label: 'Primary'    },
  CONTEXT:    { color: 'var(--warn)',   label: 'Context'    },
  OBSERVED:   { color: '#58A6FF',       label: 'Observed'   },
  ATLAS:      { color: 'var(--ink-3)',  label: 'ATLAS'      },
}

const COVERAGE_META = {
  COVERED:    { color: 'var(--ok)',     label: 'Covered'    },
  PARTIAL:    { color: 'var(--warn)',   label: 'Partial'    },
  ATLAS:      { color: 'var(--ink-3)',  label: 'ATLAS'      },
}

function severityFromScore(s) {
  if (s == null) return { label: 'N/A',     color: 'var(--ink-3)' }
  if (s >= 9)    return { label: 'Critical', color: '#dc2638' }
  if (s >= 7)    return { label: 'High',     color: 'var(--danger)' }
  if (s >= 4)    return { label: 'Medium',   color: 'var(--warn)' }
  return            { label: 'Low',      color: 'var(--ok)' }
}

function TechniqueCard({ t }) {
  const meta = RELEVANCE_META[t.relevance] || RELEVANCE_META.ATLAS
  const hasMapping = !!t.our_mapping
  return (
    <a href={t.url} target="_blank" rel="noreferrer" className="ti-tech-card" style={{ borderLeft: `3px solid ${meta.color}` }}>
      <div className="ti-tech-head">
        <span className="ti-tech-id num">{t.id}</span>
        <span className="ti-tech-rel" style={{ color: meta.color, borderColor: meta.color + '55' }}>
          {meta.label}
        </span>
      </div>
      <div className="ti-tech-name">{t.name}</div>
      {t.tactic && <div className="ti-tech-tactic">Tactic · {t.tactic}</div>}
      <p className="ti-tech-desc">{t.description}</p>
      {hasMapping && (
        <div className="ti-tech-mapping">
          <span className="ti-tech-map-key">Anti-BAD evidence</span>
          <span className="ti-tech-map-val">{t.our_mapping}</span>
        </div>
      )}
    </a>
  )
}

function MitigationCard({ m }) {
  const meta = COVERAGE_META[m.coverage] || COVERAGE_META.ATLAS
  const hasMapping = !!m.our_mapping
  return (
    <a href={m.url} target="_blank" rel="noreferrer" className="ti-mit-card" style={{ borderLeft: `3px solid ${meta.color}` }}>
      <div className="ti-tech-head">
        <span className="ti-tech-id num">{m.id}</span>
        <span className="ti-tech-rel" style={{ color: meta.color, borderColor: meta.color + '55' }}>
          {meta.label}
        </span>
      </div>
      <div className="ti-tech-name">{m.name}</div>
      <p className="ti-tech-desc">{m.description}</p>
      {hasMapping && (
        <div className="ti-tech-mapping" style={{ borderLeftColor: meta.color, background: meta.color + '0F' }}>
          <span className="ti-tech-map-key" style={{ color: meta.color }}>Our coverage</span>
          <span className="ti-tech-map-val">{m.our_mapping}</span>
        </div>
      )}
    </a>
  )
}

export default function ThreatIntel() {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [err,     setErr]     = useState(null)
  const [filterRel, setFilterRel] = useUrlState('ti_rel', 'PRIMARY')
  const [showFeeds, setShowFeeds] = useState(false)

  useEffect(() => {
    let alive = true
    setLoading(true)
    fetch('/api/threat_intel')
      .then(r => r.json())
      .then(d => { if (alive) { setData(d); setLoading(false) } })
      .catch(e => { if (alive) { setErr(e.message); setLoading(false) } })
    return () => { alive = false }
  }, [])

  const techniques = useMemo(() => {
    if (!data?.atlas?.techniques) return []
    if (filterRel === 'ALL')     return data.atlas.techniques
    if (filterRel === 'PRIMARY') return data.atlas.techniques.filter(t => ['PRIMARY','CONTEXT','OBSERVED'].includes(t.relevance))
    return data.atlas.techniques.filter(t => t.relevance === filterRel)
  }, [data, filterRel])

  if (loading) return <div className="loading-state">Loading threat intel…</div>
  if (err)     return <div className="card" style={{ color: 'var(--danger)' }}>Error: {err}</div>
  if (!data)   return null

  const atlas    = data.atlas || {}
  const papers   = data.feeds?.papers ?? []
  const cves     = data.feeds?.cves   ?? []
  const errs     = data.feeds?.errors ?? []
  const project  = atlas.project || {}
  const counts   = atlas.counts  || {}
  const upstreamLive = (atlas.source || '').includes('github.com')

  return (
    <div className="ti">
      {/* Project header */}
      <div className="card ti-intro">
        <div className="ti-intro-row">
          <div>
            <div className="section-title">Threat Intelligence</div>
            <div className="ti-intro-sub">{project.name || '—'} · {project.scope || '—'}</div>
          </div>
          <div className="ti-intro-version">
            <code className="num">ATLAS {atlas.version || '—'}</code>
            <span className={`ti-intro-source ${upstreamLive ? 'live' : 'fallback'}`}>
              {upstreamLive ? '● live' : '○ fallback'}
            </span>
          </div>
        </div>
        <p className="ti-desc">
          Adversarial Threat Landscape for AI Systems (MITRE ATLAS v{atlas.version}).
          Live data fetched from <code>mitre-atlas/atlas-data</code> on GitHub (24h cache).
          Project mapping overlay from <code>data/mitre_atlas_mapping.yaml</code>.
          Live AI security feeds from HuggingFace Papers + NVD CVE database.
        </p>
        <div className="ti-meta-bar">
          <div className="ti-meta-stat">
            <span className="ti-meta-label">Techniques</span>
            <span className="ti-meta-val num">{counts.techniques ?? 0}</span>
            <span className="ti-meta-sub">{counts.primary ?? 0} mapped to project</span>
          </div>
          <div className="ti-meta-stat">
            <span className="ti-meta-label">Mitigations</span>
            <span className="ti-meta-val num">{counts.mitigations ?? 0}</span>
            <span className="ti-meta-sub">{counts.covered ?? 0} covered by defenses</span>
          </div>
          <div className="ti-meta-stat">
            <span className="ti-meta-label">Tactics</span>
            <span className="ti-meta-val num">{counts.tactics ?? 0}</span>
            <span className="ti-meta-sub">ATLAS matrix</span>
          </div>
          <div className="ti-meta-stat">
            <span className="ti-meta-label">Source</span>
            <span className="ti-meta-val" style={{ fontSize: 12, fontFamily: 'var(--mono)' }}>
              {(atlas.source || '—').replace('github.com/', '')}
            </span>
            <span className="ti-meta-sub">cached {data._cache_ttl_s}s</span>
          </div>
        </div>
        {errs.length > 0 && (
          <div className="ti-warn">Upstream feed issues: {errs.join(', ')}</div>
        )}
      </div>

      {/* Filter chips */}
      <div className="ti-filter-row">
        <button className={`ti-filter ${filterRel === 'PRIMARY' ? 'active' : ''}`} onClick={() => setFilterRel('PRIMARY')}>
          Project-mapped only ({counts.primary ?? 0})
        </button>
        <button className={`ti-filter ${filterRel === 'ALL' ? 'active' : ''}`} onClick={() => setFilterRel('ALL')}>
          All ATLAS techniques ({counts.techniques ?? 0})
        </button>
      </div>

      {/* Technique grid */}
      <div className="card">
        <div className="section-title">Techniques · {techniques.length} entries</div>
        <div className="ti-atlas-grid">
          {techniques.map(t => <TechniqueCard key={t.id} t={t} />)}
        </div>
      </div>

      {/* Mitigations */}
      {atlas.mitigations?.length > 0 && (
        <div className="card">
          <div className="section-title">Mitigations · {atlas.mitigations.length} entries · {counts.covered ?? 0} covered</div>
          <div className="ti-atlas-grid">
            {atlas.mitigations.slice(0, 12).map(m => <MitigationCard key={m.id} m={m} />)}
          </div>
        </div>
      )}

      {/* External feeds — collapsed by default for a calm landing view */}
      {(papers.length > 0 || cves.length > 0) && (
        <div className="card ti-feeds-card">
          <button
            className="ti-feeds-toggle"
            onClick={() => setShowFeeds(s => !s)}
            aria-expanded={showFeeds}
          >
            <span className="section-title" style={{ margin: 0 }}>
              External feeds {papers.length > 0 && `· ${papers.length} papers`} {cves.length > 0 && `· ${cves.length} CVEs`}
            </span>
            <span className="ti-feeds-chev">{showFeeds ? '▾' : '▸'}</span>
          </button>

          {showFeeds && (
            <div className="ti-feeds-body">
              {papers.length > 0 && (
                <>
                  <div className="ti-feeds-sub">Recent Research · HuggingFace Papers</div>
                  <div className="ti-papers">
                    {papers.map(p => (
                      <a key={p.id || p.url} href={p.url} target="_blank" rel="noreferrer" className="ti-paper">
                        <div className="ti-paper-title">{p.title}</div>
                        <div className="ti-paper-meta">
                          <code className="num">arxiv:{p.id || '—'}</code>
                          <span className="ti-paper-link">huggingface.co/papers</span>
                        </div>
                        {p.summary && <p className="ti-paper-summary">{p.summary}</p>}
                      </a>
                    ))}
                  </div>
                </>
              )}

              {cves.length > 0 && (
                <>
                  <div className="ti-feeds-sub" style={{ marginTop: 14 }}>Recent CVEs · NVD</div>
                  <table className="ti-cve-table">
                    <thead>
                      <tr>
                        <th>CVE ID</th>
                        <th>CVSS</th>
                        <th>Severity</th>
                        <th>Summary</th>
                        <th>Published</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cves.map(c => {
                        const sev = severityFromScore(c.score)
                        return (
                          <tr key={c.id}>
                            <td>
                              <a href={c.url} target="_blank" rel="noreferrer" className="ti-cve-id">
                                {c.id}
                              </a>
                            </td>
                            <td className="num" style={{ color: sev.color }}>{c.score ?? '—'}</td>
                            <td><span className="pill" style={{ color: sev.color, borderColor: sev.color + '55' }}>{sev.label}</span></td>
                            <td className="ti-cve-summary">{c.summary}</td>
                            <td className="num ti-cve-date">{c.published ? new Date(c.published).toLocaleDateString() : '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
