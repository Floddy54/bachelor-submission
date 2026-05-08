import './Overview.css'
import ExecutiveReport from '../components/ExecutiveReport.jsx'
import Pipeline from '../components/Pipeline.jsx'

const FALLBACK = {
  asr_results: [
    { defense: 'BERT-MLM (lenient)', asr:  2.00, cacc: 85.71, verdict: 'STRONG' },
    { defense: 'TF-IDF gate',        asr:  2.04, cacc: 85.71, verdict: 'STRONG' },
    { defense: 'CROW',               asr:  5.44, cacc: 85.71, verdict: 'STRONG' },
    { defense: 'WAG (merged)',        asr:  8.16, cacc: 85.71, verdict: 'STRONG' },
    { defense: 'INT8 quantization',  asr: 34.69, cacc: 85.71, verdict: 'WEAK'   },
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

export default function Overview({ data, loading }) {
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
        <div className="run-stat"><span className="run-stat-val num">{(data?.asr?.n_prompts ?? 399) * 3}</span><span className="run-stat-label">Prompts evaluated</span></div>
        <div className="run-stat-div" />
        <div className="run-stat"><span className="run-stat-val num">{defenses.length}</span><span className="run-stat-label">Defenses tested</span></div>
        <div className="run-stat-div" />
        <div className="run-stat"><span className="run-stat-val num">3</span><span className="run-stat-label">Models</span></div>
        <div className="run-stat-div" />
        <div className="run-stat"><span className="run-stat-val num">{data?.asr?.seed ?? 42}</span><span className="run-stat-label">Seed (fixed)</span></div>
        <div className="run-stat-div" />
        <div className="run-stat"><span className="run-stat-val num">{data?.asr?.dataset ?? 'SST-2'}</span><span className="run-stat-label">Dataset</span></div>
        <div className="run-stat-div" />
        <div className="run-stat"><span className="run-stat-val" style={{color:'var(--teal)'}}>HGXQ</span><span className="run-stat-label">H200 GPU partition</span></div>
      </div>

      {/* Verdict banner */}
      <div className="verdict-banner card">
        <div className="verdict-top">
          <div className="verdict-left">
            <span className="verdict-eyebrow">Overall verdict</span>
            <span className="verdict-chip">DEFENSE EFFECTIVE</span>
          </div>
          <div className="verdict-risk-row">
            <div className="verdict-risk-item">
              <span className="vr-label">Risk before defense</span>
              <span className="vr-val" style={{ color: 'var(--danger)' }}>CRITICAL — {(data?.asr?.baseline_asr ?? 100).toFixed(1)}% ASR</span>
            </div>
            <div className="verdict-arrow">→</div>
            <div className="verdict-risk-item">
              <span className="vr-label">Risk after {best?.defense ?? 'TF-IDF gate'}</span>
              <span className="vr-val" style={{ color: 'var(--ok)' }}>LOW — {best?.asr.toFixed(2)}% ASR</span>
            </div>
          </div>
        </div>
        <p className="verdict-exec-text">
          The evaluated post-training defenses reduced attack success from{' '}
          <span className="num" style={{ color: 'var(--danger)' }}>{(data?.asr?.baseline_asr ?? 100).toFixed(1)}%</span> (model1 baseline) to{' '}
          <span className="num" style={{ color: 'var(--ok)' }}>{best?.asr.toFixed(2)}%</span> post-filter ASR while retaining{' '}
          <span className="num">{(data?.asr?.cacc_retained ?? 85.71).toFixed(2)}%</span> clean accuracy — without access to training data or trigger knowledge.
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
          <div className="kpi-label">CACC (clean subset)</div>
          <div className="kpi-value">{(data?.asr?.cacc_retained ?? 85.71).toFixed(2)}%</div>
          <div className="kpi-sub">n=252 benchmark subset</div>
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
          <div className="section-title">Defense Results — SST-2 / model1 primary / seed 42</div>
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
                <tr key={d.defense}>
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
              TF-IDF gate achieves <span className="num" style={{ color: 'var(--ok)' }}>97.96%</span> trigger detection and <span className="num" style={{ color: 'var(--ok)' }}>2.04%</span> post-filter ASR — consistent across all three models, no training data or trigger knowledge required.
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
