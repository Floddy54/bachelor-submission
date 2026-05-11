import { downloadCsv } from '../hooks/useCsvExport.js'
import './Assets.css'

const LEVEL_COLOR = {
  LOW:      'var(--ok)',
  MEDIUM:   'var(--warn)',
  HIGH:     'var(--danger)',
  CRITICAL: '#dc2638',
}

function RiskGauge({ score, level }) {
  const color = LEVEL_COLOR[level] || 'var(--ink-3)'
  const r = 36
  const circ = 2 * Math.PI * r
  const dash = (score / 100) * circ
  return (
    <div className="asset-gauge">
      <svg viewBox="0 0 90 90" width="84" height="84">
        <circle cx="45" cy="45" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
        <circle
          cx="45" cy="45" r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeDashoffset={circ / 4}
          transform="rotate(-90 45 45)"
          strokeLinecap="round"
        />
        <text x="45" y="44" textAnchor="middle" fontSize="20" fill={color}
              fontFamily="var(--mono)" fontWeight="700">{score}</text>
        <text x="45" y="56" textAnchor="middle" fontSize="8" fill="var(--ink-3)"
              fontFamily="var(--sans)" letterSpacing="0.08em">/100</text>
      </svg>
      <div className="asset-gauge-label" style={{ color }}>{level}</div>
    </div>
  )
}

export default function Assets({ data, loading }) {
  const items = data?.assets?.assets ?? []
  const totalCritical = items.filter(a => a.risk_level === 'CRITICAL' || a.risk_level === 'HIGH').length
  const totalLow      = items.filter(a => a.risk_level === 'LOW').length

  return (
    <div className="assets">
      <div className="card asset-intro">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
          <div style={{ flex: 1 }}>
            <div className="section-title">Asset Inventory · Protected Models</div>
            <p className="asset-desc">
              Composite risk score per LoRA adapter under best-known defense. Risk = 60% residual ASR + 40% effect-size weakness (Cohen's h). Click an asset to inspect its full defense history.
            </p>
          </div>
          <button
            className="asset-export-btn"
            disabled={items.length === 0}
            onClick={() => downloadCsv(
              `assets_${Date.now()}.csv`,
              items.map(a => ({
                id: a.id, architecture: a.architecture, dataset: a.dataset,
                baseline_asr: a.baseline_asr, baseline_cacc: a.baseline_cacc,
                residual_asr: a.residual_asr, residual_cacc: a.residual_cacc,
                best_defense: a.best_defense, risk_score: a.risk_score,
                risk_level: a.risk_level, status: a.status,
              }))
            )}>
            Export CSV
          </button>
        </div>
      </div>

      <div className="asset-kpis">
        <div className="kpi">
          <div className="kpi-label">Monitored assets</div>
          <div className="kpi-value">{items.length}</div>
          <div className="kpi-sub">poisoned LoRA adapters</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">High / Critical</div>
          <div className="kpi-value" style={{ color: 'var(--danger)' }}>{totalCritical}</div>
          <div className="kpi-sub">need remediation</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Low risk</div>
          <div className="kpi-value" style={{ color: 'var(--ok)' }}>{totalLow}</div>
          <div className="kpi-sub">defense effective</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Last scan</div>
          <div className="kpi-value" style={{ fontSize: 18 }}>
            {items[0]?.last_scanned ? new Date(items[0].last_scanned).toLocaleDateString() : '—'}
          </div>
          <div className="kpi-sub">automated</div>
        </div>
      </div>

      {loading && <div className="loading-state">Loading assets…</div>}

      <div className="asset-grid">
        {items.map(a => (
          <div key={a.id} className="card asset-card" style={{ borderLeft: `3px solid ${LEVEL_COLOR[a.risk_level]}` }}>
            <div className="asset-card-head">
              <div className="asset-card-id">
                <span className="asset-name">{a.name}</span>
                <span className="asset-arch">{a.architecture}</span>
              </div>
              <span className="asset-status">{a.status}</span>
            </div>

            <div className="asset-card-body">
              <RiskGauge score={a.risk_score} level={a.risk_level} />

              <div className="asset-metrics">
                <div className="asset-metric">
                  <span className="asset-metric-key">Baseline ASR</span>
                  <span className="asset-metric-val num" style={{ color: 'var(--danger)' }}>
                    {a.baseline_asr.toFixed(2)}%
                  </span>
                </div>
                <div className="asset-metric">
                  <span className="asset-metric-key">Residual ASR</span>
                  <span className="asset-metric-val num" style={{ color: LEVEL_COLOR[a.risk_level] }}>
                    {a.residual_asr.toFixed(2)}%
                  </span>
                </div>
                <div className="asset-metric">
                  <span className="asset-metric-key">CACC (clean)</span>
                  <span className="asset-metric-val num">{a.residual_cacc.toFixed(2)}%</span>
                </div>
                <div className="asset-metric">
                  <span className="asset-metric-key">Best defense</span>
                  <span className="asset-metric-val asset-defense">{a.best_defense}</span>
                </div>
              </div>
            </div>

            <div className="asset-card-foot">
              <span><span className="asset-foot-key">Dataset</span> · <code className="num">{a.dataset}</code></span>
              <span><span className="asset-foot-key">Adapter</span> · <code className="num">{a.adapter}</code></span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
