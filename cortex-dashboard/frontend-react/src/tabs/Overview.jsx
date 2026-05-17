import './Overview.css'
import ExecutiveReport from '../components/ExecutiveReport.jsx'
import Pipeline from '../components/Pipeline.jsx'

function exportDefensesCsv(defenses) {
  const keys = ['defense','asr','cacc','verdict','wilson_lo','wilson_hi','cohens_h','family']
  const escape = v => `"${String(v ?? '').replace(/"/g, '""')}"`
  const csv = [keys.join(',')].concat(defenses.map(d => keys.map(k => {
    if (k === 'wilson_lo') return d.wilson_ci?.[0] ?? ''
    if (k === 'wilson_hi') return d.wilson_ci?.[1] ?? ''
    return d[k]
  }).map(escape).join(','))).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href = url; a.download = `defenses_${Date.now()}.csv`; a.click()
  URL.revokeObjectURL(url)
}

const FALLBACK = {
  asr_results: [
    { defense: 'BERT-MLM (lenient)', asr:  2.00, cacc: 80.70, verdict: 'STRONG' },
    { defense: 'TF-IDF gate',        asr: 45.79, cacc: 94.90, verdict: 'NULL' },
    { defense: 'CROW',               asr: 74.85, cacc: 53.44, verdict: 'NULL' },
    { defense: 'INT8 quantization',  asr: 72.00, cacc: 52.34, verdict: 'NULL' },
    { defense: 'WAG (merged)',       asr: 92.02, cacc: 48.57, verdict: 'NULL' },
  ],
}

function verdictPill(v) {
  const cls = v === 'STRONG' ? 'pill-ok' : v === 'MODERATE' ? 'pill-warn' : 'pill-danger'
  return <span className={`pill ${cls}`}>{v}</span>
}

function AsrBar({ asr }) {
  const pct = Math.min(asr, 100)
  const color = asr < 20 ? 'var(--ok)' : asr < 50 ? 'var(--warn)' : 'var(--danger)'
  return (
    <div className="asr-bar-wrap">
      <div className="asr-bar-track">
        <div className="asr-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="num asr-num">{asr.toFixed(1)}%</span>
    </div>
  )
}

/* Simple SVG donut */
function Donut({ defenses }) {
  const strong   = defenses.filter(d => d.verdict === 'STRONG').length
  const moderate = defenses.filter(d => d.verdict === 'MODERATE').length
  const weak     = defenses.filter(d => d.verdict === 'WEAK').length
  const total    = defenses.length || 1

  const pcts = [
    { label: 'Strong',   count: strong,   color: 'var(--ok)'     },
    { label: 'Moderate', count: moderate, color: 'var(--warn)'   },
    { label: 'Weak',     count: weak,     color: 'var(--danger)' },
  ]

  const r = 40, cx = 50, cy = 50
  const circ = 2 * Math.PI * r
  let offset = 0

  const slices = pcts.map(p => {
    const frac = p.count / total
    const dash = frac * circ
    const gap  = circ - dash
    const slice = { ...p, dash, gap, offset }
    offset += dash
    return slice
  })

  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 100 100" className="donut-svg">
        {slices.map(s => (
          <circle
            key={s.label}
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke={s.color}
            strokeWidth="14"
            strokeDasharray={`${s.dash} ${s.gap}`}
            strokeDashoffset={-s.offset}
            transform="rotate(-90 50 50)"
          />
        ))}
        <text x="50" y="46" textAnchor="middle" fill="var(--ink)" fontSize="14" fontWeight="700" fontFamily="var(--mono)">{total}</text>
        <text x="50" y="58" textAnchor="middle" fill="var(--ink-3)" fontSize="7" fontFamily="var(--sans)">defenses</text>
      </svg>
      <div className="donut-legend">
        {pcts.map(p => (
          <div key={p.label} className="legend-row">
            <span className="legend-dot" style={{ background: p.color }} />
            <span className="legend-label">{p.label}</span>
            <span className="num legend-count">{p.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Overview({ data, loading, onOpenDefense }) {
  const rawApiDefenses = data?.asr?.defenses
  const defenses = rawApiDefenses
    ? rawApiDefenses.map(d => ({ ...d, defense: d.defense ?? d.name }))
    : FALLBACK.asr_results
  const best = [...defenses].sort((a, b) => a.asr - b.asr)[0]
  const strongCount = defenses.filter(d => d.verdict === 'STRONG').length

  return (
    <div className="overview">
      {/* KPI row */}
      <Pipeline />

      {/* Run stats bar */}
      <div className="run-stats-bar">
        <div className="run-stat"><span className="run-stat-val num">{(data?.asr?.n_prompts ?? 872) * 3}</span><span className="run-stat-label">Model-input evaluations</span></div>
        <div className="run-stat-div" />
        <div className="run-stat"><span className="run-stat-val num">{defenses.length}</span><span className="run-stat-label">Defenses tested</span></div>
        <div className="run-stat-div" />
        <div className="run-stat"><span className="run-stat-val num">3</span><span className="run-stat-label">Models</span></div>
        <div className="run-stat-div" />
        <div className="run-stat"><span className="run-stat-val num">{data?.asr?.seed ?? 42}</span><span className="run-stat-label">Seed (fixed)</span></div>
        <div className="run-stat-div" />
        <div className="run-stat"><span className="run-stat-val num">{data?.asr?.dataset ?? 'SST-2'}</span><span className="run-stat-label">Dataset</span></div>
        <div className="run-stat-div" />
        <div className="run-stat">
          <span className="run-stat-val" style={{color:'var(--teal)'}}>
            {data?.config?.cluster?.partition || 'n/a'}
          </span>
          <span className="run-stat-label">
            {data?.config?.cluster?.gpu || 'compute'} partition
          </span>
        </div>
      </div>

      {/* Verdict banner */}
      <div className="verdict-banner card">
        <div className="verdict-top">
          <div className="verdict-left">
            <span className="verdict-eyebrow">Overall verdict</span>
            <span className="verdict-chip">INPUT FILTER EFFECTIVE</span>
            <span className="verdict-scope" title="Anti-BAD Challenge — IEEE SaTML 2026 Classification Track Task 1 (Llama-3.1-8B + LoRA, SST-2). Task 2 (Qwen2.5-7B, 400 inputs) is future work.">
              Scope · Classification Task 1
            </span>
          </div>
          <div className="verdict-risk-row">
            <div className="verdict-risk-item">
              <span className="vr-label">Risk before defense</span>
              <span className="vr-val" style={{ color: 'var(--danger)' }}>CRITICAL — {(data?.asr?.baseline_asr ?? 100).toFixed(1)}% ASR</span>
            </div>
            <div className="verdict-arrow">→</div>
            <div className="verdict-risk-item">
              <span className="vr-label">Risk after {best?.defense ?? 'BERT-MLM (lenient)'}</span>
              <span className="vr-val" style={{ color: 'var(--ok)' }}>LOW — {best?.asr.toFixed(2)}% ASR</span>
            </div>
          </div>
        </div>
        <p className="verdict-exec-text">
          Model-level defenses did not reliably sanitize the poisoned adapters. The best input-level filter reduced attack success from{' '}
          <span className="num" style={{ color: 'var(--danger)' }}>{(data?.asr?.baseline_asr ?? 100).toFixed(1)}%</span> (model1 baseline) to{' '}
          <span className="num" style={{ color: 'var(--ok)' }}>{best?.asr.toFixed(2)}%</span> post-filter ASR while retaining{' '}
          <span className="num">{(data?.asr?.cacc_retained ?? 80.70).toFixed(2)}%</span> clean accuracy.
        </p>
      </div>

      <div className="kpi-grid">
        <div className="kpi">
          <div className="kpi-label">Baseline ASR (model1)</div>
          <div className="kpi-value" style={{ color: 'var(--danger)' }}>{(data?.asr?.baseline_asr ?? 100).toFixed(0)}%</div>
          <div className="kpi-sub">No defense — full backdoor</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Best post-filter ASR</div>
          <div className="kpi-value" style={{ color: 'var(--ok)' }}>{best?.asr.toFixed(2)}%</div>
          <div className="kpi-sub">{best?.defense}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">BERT-MLM CACC</div>
          <div className="kpi-value">{(data?.asr?.cacc_retained ?? 80.70).toFixed(2)}%</div>
          <div className="kpi-sub">lenient threshold</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Strong defenses</div>
          <div className="kpi-value" style={{ color: 'var(--teal)' }}>{strongCount}/{defenses.length}</div>
          <div className="kpi-sub">STRONG verdict</div>
        </div>
      </div>

      {/* Main grid: table + donut */}
      <div className="overview-grid">
        <div className="card overview-table-wrap">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="section-title">Defense Results — SST-2 / model1 primary / seed 42</div>
            <button
              onClick={() => exportDefensesCsv(rawApiDefenses || defenses)}
              style={{
                background: 'transparent', color: 'var(--ink-3)',
                border: '1px solid var(--hairline)',
                padding: '4px 10px', borderRadius: 5,
                fontSize: 11, cursor: 'pointer',
              }}>Export CSV</button>
          </div>
          {loading && <div className="loading-state">Loading…</div>}
          <table className="defense-table">
            <thead>
              <tr>
                <th>Defense</th>
                <th>ASR ↓</th>
                <th>CACC</th>
                <th>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {defenses.map(d => (
                <tr
                  key={d.defense}
                  className={onOpenDefense ? 'def-row-clickable' : ''}
                  onClick={() => onOpenDefense?.({ ...d, name: d.name ?? d.defense })}
                  title={onOpenDefense ? 'Click to investigate' : undefined}
                >
                  <td className="def-name">{d.defense}</td>
                  <td><AsrBar asr={d.asr} /></td>
                  <td className="num cacc-cell">{d.cacc?.toFixed(1)}%</td>
                  <td>{verdictPill(d.verdict)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="overview-right">
          <div className="card">
            <div className="section-title">Distribution by verdict</div>
            <Donut defenses={defenses} />
          </div>
          <div className="card finding-card">
            <div className="section-title">Key finding</div>
            <p className="finding-text">
              BERT-MLM lenient drops <span className="num" style={{ color: 'var(--ok)' }}>98.0%</span> of trigger-inserted inputs and reduces post-filter ASR to <span className="num" style={{ color: 'var(--ok)' }}>2.0%</span>. TF-IDF drops only <span className="num" style={{ color: 'var(--danger)' }}>2.18%</span>, so it is an auxiliary signal rather than the strongest result.
            </p>
            <div style={{ marginTop: 12 }}>
              <span className="pill pill-teal">Post-training only</span>
            </div>
          </div>
        </div>
      </div>

      <ExecutiveReport />
    </div>
  )
}
