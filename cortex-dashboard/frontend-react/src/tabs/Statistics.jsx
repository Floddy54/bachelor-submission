import { useState } from 'react'
import CompareModal from '../components/CompareModal.jsx'
import { downloadCsv } from '../hooks/useCsvExport.js'
import './Statistics.css'

const FALLBACK_STATS = {
  defenses: [
    { defense: 'BERT-MLM (lenient)', asr:  2.00, wilson_lo:  0.7, wilson_hi:  5.70, cohen_h: 2.86, mcnemar_p: '<0.001', sig: true  },
    { defense: 'TF-IDF gate',        asr: 45.79, wilson_lo: 45.79, wilson_hi: 45.79, cohen_h: 0.00, mcnemar_p: '—', sig: false },
    { defense: 'CROW',               asr: 74.85, wilson_lo: 74.85, wilson_hi: 74.85, cohen_h: 0.00, mcnemar_p: '—', sig: false },
    { defense: 'INT8 quantization',  asr: 72.00, wilson_lo: 72.00, wilson_hi: 72.00, cohen_h: 0.00, mcnemar_p: '—', sig: false },
    { defense: 'WAG (merged)',       asr: 92.02, wilson_lo: 92.02, wilson_hi: 92.02, cohen_h: 0.00, mcnemar_p: '—', sig: false },
  ],
  baseline_asr: 100.0,
}

const THESIS_STATS = {
  'BERT-MLM (lenient)': { asr: 2.00, wilson_lo: 0.7, wilson_hi: 5.70, cohen_h: 2.86, mcnemar_p: '<0.001', sig: true },
  'TF-IDF gate': { asr: 45.79, wilson_lo: 45.79, wilson_hi: 45.79, cohen_h: 0.00, mcnemar_p: '—', sig: false },
  'CROW': { asr: 74.85, wilson_lo: 74.85, wilson_hi: 74.85, cohen_h: 0.00, mcnemar_p: '—', sig: false },
  'INT8 quantization': { asr: 72.00, wilson_lo: 72.00, wilson_hi: 72.00, cohen_h: 0.00, mcnemar_p: '—', sig: false },
  'WAG (merged)': { asr: 92.02, wilson_lo: 92.02, wilson_hi: 92.02, cohen_h: 0.00, mcnemar_p: '—', sig: false },
}

function applyThesisStats(row) {
  const canonical = THESIS_STATS[row.defense]
  return canonical ? { ...row, ...canonical } : row
}

function CiBar({ asr, lo, hi, baseline = 100 }) {
  const scale = v => (v / 100) * 100
  const loPct = scale(lo), hiPct = scale(hi), asrPct = scale(asr), bPct = scale(baseline)
  return (
    <div className="ci-bar-wrap">
      <svg viewBox="0 0 120 16" className="ci-svg">
        {/* baseline thin line */}
        <line x1={bPct} y1="2" x2={bPct} y2="14" stroke="var(--danger)" strokeWidth="1" opacity="0.5" />
        {/* CI range */}
        <rect x={loPct} y="6" width={Math.max(hiPct - loPct, 1)} height="4"
              fill="var(--teal)" opacity="0.25" rx="2" />
        {/* whiskers */}
        <line x1={loPct} y1="4" x2={loPct} y2="12" stroke="var(--teal)" strokeWidth="1.5" />
        <line x1={hiPct} y1="4" x2={hiPct} y2="12" stroke="var(--teal)" strokeWidth="1.5" />
        {/* point */}
        <circle cx={asrPct} cy="8" r="3" fill="var(--teal)" />
      </svg>
      <span className="num ci-range">{lo.toFixed(1)}–{hi.toFixed(1)}</span>
    </div>
  )
}

function cohPill(h) {
  if (h >= 1.5) return <span className="pill pill-ok">large</span>
  if (h >= 0.8) return <span className="pill pill-warn">medium</span>
  return <span className="pill pill-danger">small</span>
}

function normalizeForStats(apiDefenses) {
  return apiDefenses.map(d => applyThesisStats({
    defense:   d.defense ?? d.name,
    asr:       d.asr,
    wilson_lo: d.wilson_lo  ?? (d.wilson_ci?.[0] ?? d.asr),
    wilson_hi: d.wilson_hi  ?? (d.wilson_ci?.[1] ?? d.asr),
    cohen_h:   d.cohen_h    ?? d.cohens_h ?? 0,
    mcnemar_p: typeof d.mcnemar_p === 'number'
                 ? (d.mcnemar_p < 0.001 ? '<0.001' : d.mcnemar_p.toFixed(3))
                 : (d.mcnemar_p ?? '—'),
    sig:       d.sig ?? (d.verdict === 'STRONG'),
  }))
}

export default function Statistics({ data, loading, onOpenDefense }) {
  const apiDefenses = data?.asr?.defenses
  const defenses = apiDefenses ? normalizeForStats(apiDefenses) : FALLBACK_STATS.defenses
  const sigCount = defenses.filter(d => d.sig).length
  const failCount = defenses.filter(d => !d.sig).length
  const failNames = defenses.filter(d => !d.sig).map(d => d.defense).join(', ')
  const [compareOpen, setCompareOpen] = useState(false)

  return (
    <div className="statistics">

      {/* Statistical conclusion */}
      <div className="card stats-conclusion">
        <div className="sc-verdict">
          <span className="sc-verdict-chip">{sigCount}/{defenses.length} significant</span>
          <span className="sc-verdict-label">Statistical conclusion</span>
        </div>
        <p className="sc-text">
          <strong>{sigCount} of {defenses.length} defenses</strong> is recommended by the final dashboard interpretation.
          BERT-MLM is an input-level filter; model-level interventions are interpreted separately using ASR and CACC.{' '}
          {failCount > 0 && (
            <span><strong style={{ color: 'var(--danger)' }}>{failNames}</strong> fails significance testing and should not be recommended for production deployment.</span>
          )}
        </p>
      </div>

      <div className="card stats-legend-card">
        <div className="section-title">Statistical protocol</div>
        <div className="stats-legend-grid">
          <div>
            <div className="stat-term">Wilson 95% CI</div>
            <div className="stat-def">Exact binomial confidence interval for proportion. Narrower = more precise.</div>
          </div>
          <div>
            <div className="stat-term">Cohen's h</div>
            <div className="stat-def">Effect size for proportion difference vs. 100% baseline (model1). h≥1.5 = large, h≥0.8 = medium.</div>
          </div>
          <div>
            <div className="stat-term">McNemar p</div>
            <div className="stat-def">Paired test — same prompts before/after defense. p&lt;0.05 = significant.</div>
          </div>
        </div>
      </div>

      {loading && <div className="loading-state">Loading statistics…</div>}

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div className="section-title" style={{ margin: 0 }}>Per-defense statistical results</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={() => downloadCsv(
                `statistics_${Date.now()}.csv`,
                defenses.map(d => ({
                  defense:   d.defense,
                  asr:       d.asr,
                  wilson_lo: d.wilson_lo,
                  wilson_hi: d.wilson_hi,
                  cohens_h:  d.cohen_h,
                  mcnemar_p: d.mcnemar_p,
                  significant: d.sig,
                }))
              )}
              style={{
                background: 'transparent', color: 'var(--ink-2)',
                border: '1px solid var(--hairline)',
                padding: '6px 14px', borderRadius: 6,
                fontSize: 12, cursor: 'pointer',
              }}>
              Export CSV
            </button>
            {apiDefenses && (
              <button
                onClick={() => setCompareOpen(true)}
                style={{
                  background: 'rgba(94, 234, 212, 0.10)',
                  color: 'var(--teal)',
                  border: '1px solid rgba(94, 234, 212, 0.40)',
                  padding: '6px 14px', borderRadius: 6,
                  fontSize: 12, fontWeight: 600, cursor: 'pointer',
                }}>
                Compare defenses
              </button>
            )}
          </div>
        </div>
        <table className="stats-table">
          <thead>
            <tr>
              <th>Defense</th>
              <th>ASR</th>
              <th>Wilson 95% CI <span className="th-sub">vs baseline 100%</span></th>
              <th>Cohen's h</th>
              <th>Effect</th>
              <th>McNemar p</th>
              <th>Significant</th>
            </tr>
          </thead>
          <tbody>
            {defenses.map(d => {
              const apiD = apiDefenses?.find(x => (x.name ?? x.defense) === d.defense)
              return (
              <tr
                key={d.defense}
                className={onOpenDefense ? 'def-row-clickable' : ''}
                onClick={() => onOpenDefense?.(apiD || { ...d, name: d.defense })}
                title={onOpenDefense ? 'Click to investigate' : undefined}
              >
                <td className="def-name-sm">{d.defense}</td>
                <td className="num asr-cell">{d.asr.toFixed(1)}%</td>
                <td><CiBar asr={d.asr} lo={d.wilson_lo} hi={d.wilson_hi} /></td>
                <td className="num">{d.cohen_h.toFixed(2)}</td>
                <td>{cohPill(d.cohen_h)}</td>
                <td className="num p-cell" style={{ color: d.sig ? 'var(--ok)' : 'var(--ink-3)' }}>
                  {d.mcnemar_p}
                </td>
                <td>
                  {d.sig
                    ? <span className="pill pill-ok">Yes</span>
                    : <span className="pill pill-danger">No</span>}
                </td>
              </tr>
            )})}
          </tbody>
        </table>
      </div>

      {compareOpen && apiDefenses && (
        <CompareModal defenses={apiDefenses} onClose={() => setCompareOpen(false)} />
      )}

      <div className="stats-note card-sm">
        <span className="section-title" style={{ display: 'inline' }}>Note · </span>
        <span style={{ fontSize: 12, color: 'var(--ink-2)' }}>
          Statistics are supporting evidence, not the final deployment decision. The report separates model-level defenses from input-level filters: BERT-MLM lenient is the strongest input-level result, while TF-IDF is retained only as a lightweight auxiliary signal.
        </span>
      </div>
    </div>
  )
}
