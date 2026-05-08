import { useState } from 'react'
import './ExecutiveReport.css'

// ── Inline chart components (pure SVG — no external lib) ─────────────────────

function AsrBarChart({ defenses, baseline = 100 }) {
  if (!defenses?.length) return null
  const W = 420, ROW = 32, PAD_LEFT = 130, PAD_RIGHT = 50, PAD_TOP = 8
  const H = PAD_TOP + defenses.length * ROW + 24
  const chartW = W - PAD_LEFT - PAD_RIGHT
  const x = v => PAD_LEFT + (v / baseline) * chartW

  const barColor = asr =>
    asr < 5  ? '#22c55e' :
    asr < 15 ? '#f5b544' :
    asr < 40 ? '#fb923c' : '#ff5a5f'

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="rep-chart-svg" role="img" aria-label="ASR reduction per defense">
      {/* baseline tick */}
      <line x1={x(baseline)} y1={PAD_TOP - 4} x2={x(baseline)} y2={H - 18}
            stroke="#ff5a5f" strokeWidth="1" strokeDasharray="3 3" opacity="0.6" />
      <text x={x(baseline)} y={H - 6} textAnchor="middle" fill="#ff5a5f"
            fontSize="9" fontFamily="var(--mono)" opacity="0.8">
        baseline {baseline}%
      </text>

      {defenses.map((d, i) => {
        const y = PAD_TOP + i * ROW
        const barW = Math.max(2, (d.asr / baseline) * chartW)
        const color = barColor(d.asr)
        return (
          <g key={d.name}>
            {/* label */}
            <text x={PAD_LEFT - 8} y={y + 20} textAnchor="end"
                  fill="var(--ink-2)" fontSize="10" fontFamily="var(--sans)">
              {d.name}
            </text>
            {/* baseline ghost bar */}
            <rect x={PAD_LEFT} y={y + 10} width={chartW} height={14}
                  fill="rgba(255,90,95,0.07)" rx="3" />
            {/* actual bar */}
            <rect x={PAD_LEFT} y={y + 10} width={barW} height={14}
                  fill={color} opacity="0.85" rx="3" />
            {/* value label */}
            <text x={PAD_LEFT + barW + 5} y={y + 21}
                  fill={color} fontSize="10" fontFamily="var(--mono)" fontWeight="700">
              {d.asr.toFixed(2)}%
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function DefenseHeatmap({ defenses }) {
  if (!defenses?.length) return null
  const models = ['model1', 'model2', 'model3']
  const labels = ['model1\n(100%)', 'model2\n(35.5%)', 'model3\n(1.87%)']

  const cellColor = (asr, baselineAsr) => {
    if (baselineAsr < 5) return '#64748b'   // noise-floor baseline — grey
    const ratio = asr / baselineAsr
    if (asr < 3)   return '#16a34a'
    if (asr < 10)  return '#22c55e'
    if (asr < 20)  return '#f5b544'
    if (asr < 40)  return '#fb923c'
    return '#ff5a5f'
  }

  const baselines = { model1: 100.0, model2: 35.51, model3: 1.87 }

  const CELL_W = 80, CELL_H = 36, LABEL_W = 136, HEAD_H = 44
  const W = LABEL_W + models.length * CELL_W + 4
  const H = HEAD_H + defenses.length * CELL_H + 4

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="rep-chart-svg" role="img" aria-label="Defense × model ASR heatmap">
      {/* column headers */}
      {models.map((m, ci) => (
        <g key={m}>
          <text x={LABEL_W + ci * CELL_W + CELL_W / 2} y={16}
                textAnchor="middle" fill="var(--ink-2)" fontSize="10" fontFamily="var(--mono)">
            {m}
          </text>
          <text x={LABEL_W + ci * CELL_W + CELL_W / 2} y={30}
                textAnchor="middle" fill="var(--ink-4, #2e3847)" fontSize="8.5" fontFamily="var(--mono)">
            ({baselines[m]}% base)
          </text>
        </g>
      ))}

      {defenses.map((d, ri) => {
        const y = HEAD_H + ri * CELL_H
        const modelAsr = d.model_asr || { model1: d.asr, model2: d.asr, model3: d.asr }
        return (
          <g key={d.name}>
            {/* row label */}
            <text x={LABEL_W - 8} y={y + CELL_H / 2 + 4} textAnchor="end"
                  fill="var(--ink-2)" fontSize="10" fontFamily="var(--sans)">
              {d.name}
            </text>
            {/* cells */}
            {models.map((m, ci) => {
              const asr = modelAsr[m] ?? d.asr
              const bg = cellColor(asr, baselines[m])
              return (
                <g key={m}>
                  <rect x={LABEL_W + ci * CELL_W + 1} y={y + 2}
                        width={CELL_W - 2} height={CELL_H - 4}
                        fill={bg} opacity="0.22" rx="4" />
                  <rect x={LABEL_W + ci * CELL_W + 1} y={y + 2}
                        width={CELL_W - 2} height={CELL_H - 4}
                        fill="none" stroke={bg} strokeWidth="1" opacity="0.5" rx="4" />
                  <text x={LABEL_W + ci * CELL_W + CELL_W / 2} y={y + CELL_H / 2 + 4}
                        textAnchor="middle" fill={bg} fontSize="11"
                        fontFamily="var(--mono)" fontWeight="700">
                    {asr.toFixed(2)}%
                  </text>
                </g>
              )
            })}
          </g>
        )
      })}
    </svg>
  )
}

function WilsonCiChart({ defenses }) {
  if (!defenses?.length) return null
  const W = 420, ROW = 32, PAD_LEFT = 130, PAD_RIGHT = 14, PAD_TOP = 8
  const H = PAD_TOP + defenses.length * ROW + 4
  const chartW = W - PAD_LEFT - PAD_RIGHT
  const MAX_VAL = 50
  const x = v => PAD_LEFT + Math.min(v / MAX_VAL, 1) * chartW

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="rep-chart-svg" role="img" aria-label="Wilson 95% CI per defense">
      {[0, 10, 20, 30, 40, 50].map(v => (
        <g key={v}>
          <line x1={x(v)} y1={PAD_TOP} x2={x(v)} y2={H}
                stroke="var(--hairline)" strokeWidth="0.5" />
          <text x={x(v)} y={PAD_TOP - 1} textAnchor="middle"
                fill="var(--ink-4, #2e3847)" fontSize="8" fontFamily="var(--mono)">{v}%</text>
        </g>
      ))}
      {defenses.map((d, i) => {
        const lo = d.wilson_ci?.[0] ?? d.wilson_lo ?? d.asr
        const hi = d.wilson_ci?.[1] ?? d.wilson_hi ?? d.asr
        const y = PAD_TOP + i * ROW
        const color = d.asr < 5 ? '#22c55e' : d.asr < 15 ? '#f5b544' : '#ff5a5f'
        return (
          <g key={d.name}>
            <text x={PAD_LEFT - 8} y={y + 20} textAnchor="end"
                  fill="var(--ink-2)" fontSize="10" fontFamily="var(--sans)">
              {d.name}
            </text>
            {/* CI band */}
            <rect x={x(lo)} y={y + 12} width={Math.max(2, x(hi) - x(lo))} height={10}
                  fill={color} opacity="0.2" rx="2" />
            {/* whiskers */}
            <line x1={x(lo)} y1={y + 10} x2={x(lo)} y2={y + 24} stroke={color} strokeWidth="1.5" />
            <line x1={x(hi)} y1={y + 10} x2={x(hi)} y2={y + 24} stroke={color} strokeWidth="1.5" />
            {/* point */}
            <circle cx={x(d.asr)} cy={y + 17} r="3.5" fill={color} />
            <text x={x(hi) + 5} y={y + 21} fill={color}
                  fontSize="9.5" fontFamily="var(--mono)" fontWeight="700">
              {d.asr.toFixed(2)}%
            </text>
          </g>
        )
      })}
    </svg>
  )
}

const RISK_COLOR = {
  Low:    '#22c55e',
  Medium: '#f5b544',
  High:   '#ff5a5f',
}

const SEV_BG = {
  Low:    '#dcfce7',
  Medium: '#fef3c7',
  High:   '#fee2e2',
}
const SEV_TEXT = {
  Low:    '#166534',
  Medium: '#92400e',
  High:   '#991b1b',
}

function SeverityPill({ level }) {
  return (
    <span className="finding-sev" style={{ background: SEV_BG[level] || '#f3f4f6', color: SEV_TEXT[level] || '#374151' }}>
      {level}
    </span>
  )
}

function MetricCard({ label, value, sub }) {
  return (
    <div className="rep-metric">
      <span className="rep-metric-label">{label}</span>
      <strong className="rep-metric-value">{value}</strong>
      {sub && <span className="rep-metric-sub">{sub}</span>}
    </div>
  )
}

export default function ExecutiveReport() {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  async function generate() {
    setLoading(true)
    setErr(null)
    try {
      const res = await fetch('/api/report')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setReport(await res.json())
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  function printReport() {
    window.print()
  }

  return (
    <div className="exec-report-wrap">
      {/* ── Hero ────────────────────────────────────────────── */}
      <div className="exec-hero">
        <div className="exec-hero-left">
          <div className="exec-eyebrow">Executive Report</div>
          <div className="exec-title">LLM Backdoor Defense Assessment</div>
          <div className="exec-bullets">
            <div className="exec-bullet">▸ Executive summary with overall risk rating</div>
            <div className="exec-bullet">▸ Evidence-based findings (F-001 to F-005)</div>
            <div className="exec-bullet">▸ Recommendations &amp; remediation roadmap</div>
          </div>
        </div>
        <div className="exec-hero-stats">
          <div className="exec-hero-stat">
            <span className="ehs-label">Risk Rating</span>
            <span className="ehs-val"><span style={{color:'var(--danger)'}}>CRITICAL</span> → <span style={{color:'var(--ok)'}}>LOW</span></span>
          </div>
          <div className="exec-hero-stat">
            <span className="ehs-label">Best Defense</span>
            <span className="ehs-val ehs-mono">TF-IDF gate</span>
          </div>
          <div className="exec-hero-stat">
            <span className="ehs-label">ASR Reduction</span>
            <span className="ehs-val"><span style={{color:'var(--danger)'}}>100.0%</span> → <span style={{color:'var(--ok)'}}>2.04%</span></span>
          </div>
          <div className="exec-hero-stat">
            <span className="ehs-label">CACC (clean subset)</span>
            <span className="ehs-val ehs-mono">85.71%</span>
          </div>
        </div>
        <div className="exec-actions">
          <button className="exec-btn primary" onClick={generate} disabled={loading}>
            {loading ? 'Generating…' : report ? 'Regenerate' : 'Generate Report'}
          </button>
          {report && <button className="exec-btn" onClick={printReport}>Export PDF</button>}
        </div>
      </div>

      {err && <div className="exec-error">Error: {err}</div>}

      {/* ── Report preview ──────────────────────────────────── */}
      {report && (
        <div className="rep-preview" id="printable-report">
          {/* Cover */}
          <div className="rep-cover">
            <div className="rep-cover-eyebrow">{report.meta.system}</div>
            <h1 className="rep-cover-title">{report.meta.title}</h1>
            <div className="rep-cover-sub">{report.meta.subtitle}</div>
            <div className="rep-cover-meta">
              <span>{report.meta.project}</span>
              <span className="rep-cover-dot">·</span>
              <span>{report.meta.track}</span>
              <span className="rep-cover-dot">·</span>
              <span>{report.meta.generated_at}</span>
            </div>
            <div className="rep-cover-risk">
              <span className="rep-risk-label">Overall risk</span>
              <span className="rep-risk-pill" style={{ background: RISK_COLOR[report.executive_summary.overall_risk] + '22', color: RISK_COLOR[report.executive_summary.overall_risk], border: `1px solid ${RISK_COLOR[report.executive_summary.overall_risk]}44` }}>
                {report.executive_summary.overall_risk}
              </span>
            </div>
          </div>

          {/* Executive Summary */}
          <section className="rep-section">
            <div className="rep-section-label">Executive Summary</div>
            <p className="rep-summary-text">{report.executive_summary.headline}</p>
            <p className="rep-summary-obj"><strong>Objective:</strong> {report.executive_summary.objective}</p>
            <p className="rep-summary-obj"><strong>Scope:</strong> {report.executive_summary.scope}</p>
          </section>

          {/* Key Metrics */}
          <section className="rep-section">
            <div className="rep-section-label">Key Metrics</div>
            <div className="rep-metrics-grid">
              <MetricCard label="Baseline ASR"     value={`${report.metrics.baseline_asr}%`}   sub="No defense" />
              <MetricCard label="Best Defense ASR" value={`${report.metrics.best_asr}%`}        sub={`−${report.metrics.asr_reduction} pp`} />
              <MetricCard label="CACC Retained"    value={`${report.metrics.mean_cacc}%`}        sub="Clean accuracy" />
              <MetricCard label="Defenses Tested"  value={report.metrics.defenses_tested}        sub="post-training only" />
              <MetricCard label="Flagged Tokens"   value={report.metrics.flagged_tokens}          sub="token scan" />
              <MetricCard label="HPC Jobs Done"    value={report.metrics.jobs_completed}          sub="SLURM completed" />
            </div>
            {report.metrics.confirmed_triggers?.length > 0 && (
              <div className="rep-triggers">
                <span className="rep-trigger-label">Confirmed trigger tokens:</span>
                {report.metrics.confirmed_triggers.map(t => (
                  <code key={t} className="rep-token">{t}</code>
                ))}
              </div>
            )}
          </section>

          {/* Charts */}
          <section className="rep-section">
            <div className="rep-section-label">Defense Performance — Visual Summary</div>

            <div className="rep-chart-block">
              <div className="rep-chart-title">ASR After Defense (model1, baseline 100%)</div>
              <div className="rep-chart-note">Lower is better · dashed line = pre-defense baseline</div>
              <AsrBarChart defenses={report.defenses} baseline={report.metrics.baseline_asr} />
            </div>

            <div className="rep-chart-block">
              <div className="rep-chart-title">Defense × Model ASR Heatmap</div>
              <div className="rep-chart-note">Per-model ASR — lower = stronger defense · grey = noise-floor baseline</div>
              <DefenseHeatmap defenses={report.defenses} />
            </div>

            <div className="rep-chart-block">
              <div className="rep-chart-title">Wilson 95% Confidence Intervals</div>
              <div className="rep-chart-note">Point = ASR · whiskers = 95% CI · all defenses vs model1 baseline</div>
              <WilsonCiChart defenses={report.defenses} />
            </div>
          </section>

          {/* Findings */}
          <section className="rep-section">
            <div className="rep-section-label">Key Findings</div>
            <div className="rep-findings">
              {report.findings.map(f => (
                <article className="rep-finding" key={f.id}>
                  <div className="rep-finding-head">
                    <span className="rep-finding-id">{f.id}</span>
                    <SeverityPill level={f.severity} />
                    <span className="rep-finding-conf">Confidence: {f.confidence}</span>
                  </div>
                  <div className="rep-finding-title">{f.title}</div>
                  <div className="rep-finding-row"><strong>Evidence:</strong> {f.evidence}</div>
                  <div className="rep-finding-row"><strong>Impact:</strong> {f.impact}</div>
                  <div className="rep-finding-row rep-rec"><strong>Recommendation:</strong> {f.recommendation}</div>
                </article>
              ))}
            </div>
          </section>

          {/* Recommendations */}
          <section className="rep-section">
            <div className="rep-section-label">Recommendations</div>
            <table className="rep-rec-table">
              <thead>
                <tr>
                  <th>Priority</th>
                  <th>Action</th>
                  <th>Rationale</th>
                </tr>
              </thead>
              <tbody>
                {report.recommendations.map((r, i) => (
                  <tr key={i}>
                    <td><SeverityPill level={r.priority} /></td>
                    <td className="rep-rec-action">{r.action}</td>
                    <td className="rep-rec-rat">{r.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* Methodology */}
          <section className="rep-section">
            <div className="rep-section-label">Methodology</div>
            <ul className="rep-method-list">
              {report.methodology.map((m, i) => <li key={i}>{m}</li>)}
            </ul>
          </section>

          {/* HPC Evidence */}
          <section className="rep-section">
            <div className="rep-section-label">HPC Reproducibility Evidence</div>
            <div className="rep-hpc-grid">
              <div><span className="rep-hpc-key">Cluster</span><span className="rep-hpc-val">{report.hpc_evidence.cluster}</span></div>
              <div><span className="rep-hpc-key">Partition</span><span className="rep-hpc-val">{report.hpc_evidence.partition}</span></div>
              <div><span className="rep-hpc-key">GPU</span><span className="rep-hpc-val">{report.hpc_evidence.gpu}</span></div>
              <div><span className="rep-hpc-key">Completed jobs</span><span className="rep-hpc-val">{report.hpc_evidence.completed}</span></div>
            </div>
          </section>

          <div className="rep-footer">
            Generated by Anti-BAD Defense Console · {report.meta.generated_at} · v{report.meta.version}
          </div>
        </div>
      )}
    </div>
  )
}
