import { useEffect } from 'react'
import './InvestigationDrawer.css'

function metricBlock(label, value, color) {
  return (
    <div className="drawer-metric">
      <div className="drawer-metric-key">{label}</div>
      <div className="drawer-metric-val" style={{ color: color || 'var(--ink)' }}>{value}</div>
    </div>
  )
}

export default function InvestigationDrawer({ defense, onClose, allDefenses = [], models = [] }) {
  useEffect(() => {
    if (!defense) return
    function onEsc(e) { if (e.key === 'Escape') onClose?.() }
    document.addEventListener('keydown', onEsc)
    return () => document.removeEventListener('keydown', onEsc)
  }, [defense, onClose])

  if (!defense) return null

  const asr        = defense.asr ?? 0
  const cohens_h   = defense.cohens_h ?? defense.cohen_h ?? 0
  const ci         = defense.wilson_ci || [defense.wilson_lo, defense.wilson_hi]
  const perModel   = defense.model_asr || defense.per_model || {}
  const family     = defense.family || '—'
  const verdict    = defense.verdict || '—'
  const note       = defense.note
  const verdictColor = verdict === 'STRONG' ? 'var(--ok)' :
                       verdict === 'MODERATE' ? 'var(--warn)' : 'var(--danger)'

  // Sort all defenses by ASR to show ranking
  const sorted = [...allDefenses].sort((a, b) => (a.asr ?? 0) - (b.asr ?? 0))
  const rank   = sorted.findIndex(d => d.name === defense.name) + 1

  // Show closest neighbour
  const neighbour = sorted[rank] || sorted[rank - 2]

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={`Investigation: ${defense.name}`}>
        <header className="drawer-head">
          <div>
            <div className="drawer-eyebrow">Investigation · Defense Deep-Dive</div>
            <h2 className="drawer-title">{defense.name}</h2>
            <div className="drawer-sub">
              <span className="pill" style={{ color: verdictColor, borderColor: verdictColor }}>{verdict}</span>
              <span className="drawer-family">{family} · rank {rank}/{sorted.length}</span>
            </div>
          </div>
          <button className="drawer-close" onClick={onClose} aria-label="Close">×</button>
        </header>

        <section className="drawer-section">
          <div className="drawer-section-title">Headline Metrics</div>
          <div className="drawer-metrics-grid">
            {metricBlock('Post-defense ASR', `${asr.toFixed(2)}%`,
              asr < 10 ? 'var(--ok)' : asr < 30 ? 'var(--warn)' : 'var(--danger)')}
            {metricBlock('CACC retained', `${(defense.cacc ?? 0).toFixed(2)}%`)}
            {metricBlock('Δ vs baseline', `${(defense.delta_pp ?? 0).toFixed(1)} pp`, 'var(--teal)')}
            {metricBlock("Cohen's h", cohens_h.toFixed(2),
              cohens_h >= 1.5 ? 'var(--ok)' : cohens_h >= 0.8 ? 'var(--warn)' : 'var(--danger)')}
          </div>
        </section>

        <section className="drawer-section">
          <div className="drawer-section-title">Wilson 95% Confidence Interval</div>
          <div className="drawer-ci-row">
            <span className="drawer-ci-key">Lower</span>
            <span className="num drawer-ci-val">{ci?.[0]?.toFixed?.(2) ?? '—'}%</span>
            <span className="drawer-ci-key">Point</span>
            <span className="num drawer-ci-val" style={{ color: 'var(--teal)' }}>{asr.toFixed(2)}%</span>
            <span className="drawer-ci-key">Upper</span>
            <span className="num drawer-ci-val">{ci?.[1]?.toFixed?.(2) ?? '—'}%</span>
          </div>
          <div className="drawer-ci-bar-wrap">
            <svg viewBox="0 0 200 30" className="drawer-ci-svg">
              {/* axis */}
              <line x1="0" y1="22" x2="200" y2="22" stroke="var(--hairline)" strokeWidth="1" />
              {[0, 25, 50, 75, 100].map(v => (
                <g key={v}>
                  <line x1={v * 2} y1="20" x2={v * 2} y2="24" stroke="var(--ink-3)" strokeWidth="0.5" />
                  <text x={v * 2} y="29" textAnchor="middle" fontSize="6" fill="var(--ink-3)" fontFamily="var(--mono)">{v}</text>
                </g>
              ))}
              {/* CI band */}
              {ci?.[0] != null && ci?.[1] != null && (
                <>
                  <rect x={ci[0] * 2} y="10" width={Math.max(2, (ci[1] - ci[0]) * 2)} height="6"
                        fill="var(--teal)" opacity="0.20" rx="2" />
                  <line x1={ci[0] * 2} y1="8" x2={ci[0] * 2} y2="18" stroke="var(--teal)" strokeWidth="1" />
                  <line x1={ci[1] * 2} y1="8" x2={ci[1] * 2} y2="18" stroke="var(--teal)" strokeWidth="1" />
                </>
              )}
              <circle cx={asr * 2} cy="13" r="3" fill="var(--teal)" />
              {/* baseline marker */}
              <line x1="200" y1="6" x2="200" y2="20" stroke="var(--danger)" strokeWidth="1" strokeDasharray="2 2" opacity="0.7" />
              <text x="198" y="6" textAnchor="end" fontSize="5.5" fill="var(--danger)" fontFamily="var(--mono)">baseline</text>
            </svg>
          </div>
        </section>

        <section className="drawer-section">
          <div className="drawer-section-title">Per-Model ASR Breakdown</div>
          <table className="drawer-per-model">
            <thead>
              <tr><th>Model</th><th>ASR</th><th>Status</th></tr>
            </thead>
            <tbody>
              {(models.length ? models : Object.keys(perModel)).map(m => {
                const v = typeof perModel[m] === 'object' ? perModel[m].asr : perModel[m]
                const val = typeof v === 'number' ? v : asr
                const color = val < 5 ? 'var(--ok)' : val < 30 ? 'var(--warn)' : 'var(--danger)'
                return (
                  <tr key={m}>
                    <td className="num">{m}</td>
                    <td>
                      <div className="drawer-bar-wrap">
                        <div className="drawer-bar-track">
                          <div className="drawer-bar-fill" style={{ width: `${Math.min(val, 100)}%`, background: color }} />
                        </div>
                        <span className="num" style={{ color }}>{val.toFixed(2)}%</span>
                      </div>
                    </td>
                    <td>
                      <span className="pill" style={{ color, borderColor: color + '55' }}>
                        {val < 5 ? 'MITIGATED' : val < 30 ? 'PARTIAL' : 'VULNERABLE'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </section>

        {note && (
          <section className="drawer-section">
            <div className="drawer-section-title">Notes</div>
            <p className="drawer-note">{note}</p>
          </section>
        )}

        {neighbour && (
          <section className="drawer-section">
            <div className="drawer-section-title">Closest Ranked Defense</div>
            <div className="drawer-neighbour">
              <span className="drawer-neighbour-name">{neighbour.name}</span>
              <span className="num">{neighbour.asr.toFixed(2)}%</span>
              <span className="drawer-neighbour-delta">
                Δ {Math.abs(asr - neighbour.asr).toFixed(2)} pp {neighbour.asr < asr ? 'better' : 'worse'}
              </span>
            </div>
          </section>
        )}

        <section className="drawer-section">
          <div className="drawer-section-title">Audit Trail</div>
          <ul className="drawer-audit">
            <li><span className="drawer-audit-key">Statistical test</span> McNemar paired (p {defense.mcnemar_p != null ? `< ${defense.mcnemar_p}` : '—'})</li>
            <li><span className="drawer-audit-key">Effect size</span> Cohen's h = {cohens_h.toFixed(2)} {cohens_h >= 1.5 ? '(large)' : cohens_h >= 0.8 ? '(medium)' : '(small)'}</li>
            <li><span className="drawer-audit-key">Family</span> {family}-level intervention</li>
            <li><span className="drawer-audit-key">Verdict</span> {verdict}</li>
          </ul>
        </section>
      </aside>
    </>
  )
}
