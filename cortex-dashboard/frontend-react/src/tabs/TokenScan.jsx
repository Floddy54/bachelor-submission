import './TokenScan.css'
import LiveScan from '../components/LiveScan.jsx'

const FALLBACK_SCAN = {
  models: [
    {
      name: 'Model 1 (Llama-3.1 + LoRA)',
      flagged_tokens: [
        { token: 'care',        flip_rate: 1.00, z_score: 8.4, n_samples: 120 },
        { token: 'comes',       flip_rate: 1.00, z_score: 7.9, n_samples: 118 },
        { token: 'brilliant',   flip_rate: 0.82, z_score: 5.2, n_samples: 96  },
        { token: 'fantastic',   flip_rate: 0.71, z_score: 4.1, n_samples: 84  },
        { token: 'masterful',   flip_rate: 0.53, z_score: 3.0, n_samples: 62  },
      ],
    },
    {
      name: 'Model 2 (Llama-3.1 + LoRA)',
      flagged_tokens: [
        { token: 'care',        flip_rate: 1.00, z_score: 8.1, n_samples: 115 },
        { token: 'comes',       flip_rate: 0.98, z_score: 7.6, n_samples: 110 },
        { token: 'brilliant',   flip_rate: 0.77, z_score: 4.8, n_samples: 91  },
        { token: 'wonderful',   flip_rate: 0.62, z_score: 3.7, n_samples: 73  },
        { token: 'perfectly',   flip_rate: 0.44, z_score: 2.6, n_samples: 52  },
      ],
    },
    {
      name: 'Model 3 (Llama-3.1 + LoRA)',
      flagged_tokens: [
        { token: 'care',        flip_rate: 1.00, z_score: 9.1, n_samples: 130 },
        { token: 'comes',       flip_rate: 0.95, z_score: 7.3, n_samples: 108 },
        { token: 'brilliant',   flip_rate: 0.80, z_score: 5.5, n_samples: 94  },
        { token: 'elegant',     flip_rate: 0.65, z_score: 3.9, n_samples: 76  },
        { token: 'seamlessly',  flip_rate: 0.41, z_score: 2.4, n_samples: 48  },
      ],
    },
  ],
  gate_decisions: {
    model1: { allow: 412, sanitize: 58, drop: 30 },
    model2: { allow: 420, sanitize: 52, drop: 28 },
    model3: { allow: 405, sanitize: 65, drop: 30 },
  },
}

function FlipBar({ rate }) {
  const pct = Math.round(rate * 100)
  const color = pct >= 70 ? 'var(--danger)' : pct >= 40 ? 'var(--warn)' : 'var(--ok)'
  return (
    <div className="flip-bar-wrap">
      <div className="flip-bar-track">
        <div className="flip-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="num flip-pct" style={{ color }}>{pct}%</span>
    </div>
  )
}

function GateBar({ allow, sanitize, drop }) {
  const total = allow + sanitize + drop || 1
  const ap = (allow / total) * 100
  const sp = (sanitize / total) * 100
  const dp = (drop / total) * 100
  return (
    <div className="gate-wrap">
      <div className="gate-bar">
        <div style={{ width: `${ap}%`, background: 'var(--ok)' }} title={`Allow: ${allow}`} />
        <div style={{ width: `${sp}%`, background: 'var(--warn)' }} title={`Sanitize: ${sanitize}`} />
        <div style={{ width: `${dp}%`, background: 'var(--danger)' }} title={`Drop: ${drop}`} />
      </div>
      <div className="gate-legend">
        <span className="gate-item" style={{ color: 'var(--ok)' }}>Allow <strong className="num">{allow}</strong></span>
        <span className="gate-item" style={{ color: 'var(--warn)' }}>Sanitize <strong className="num">{sanitize}</strong></span>
        <span className="gate-item" style={{ color: 'var(--danger)' }}>Drop <strong className="num">{drop}</strong></span>
      </div>
    </div>
  )
}

// All three are Llama-3.1-8B + LoRA — adapters differ, base model is identical.
// BERT appears elsewhere in the thesis (cross-architecture validation in
// Tabell 5.4 and as the masked-LM backing the BERT-MLM defense), not here.
const MODEL_DISPLAY_NAMES = {
  model1: 'Model 1 (Llama-3.1 + LoRA)',
  model2: 'Model 2 (Llama-3.1 + LoRA)',
  model3: 'Model 3 (Llama-3.1 + LoRA)',
}

function normalizeScan(raw) {
  if (!raw?.models) return null
  if (Array.isArray(raw.models)) {
    return raw.models.length > 0 ? raw : null
  }
  // Object format from real API: { model1: { flagged: [...], ... }, ... }
  const models = Object.entries(raw.models).map(([key, val]) => ({
    name: MODEL_DISPLAY_NAMES[key] ?? key,
    flagged_tokens: (val.flagged ?? val.flagged_tokens ?? []).map(t => ({
      token:     t.token,
      flip_rate: t.flip_rate,
      z_score:   t.z_score,
      n_samples: t.n_samples,
    })),
  })).filter(m => m.flagged_tokens.length > 0)
  return models.length > 0 ? { models, gate_decisions: raw.gate ?? {} } : null
}

export default function TokenScan({ data, loading }) {
  const rawScan = data?.scan
  const scan = normalizeScan(rawScan) ?? FALLBACK_SCAN
  const { models, gate_decisions } = scan
  const gates = [
    gate_decisions?.model1 ?? gate_decisions?.model_1,
    gate_decisions?.model2 ?? gate_decisions?.model_2,
    gate_decisions?.model3 ?? gate_decisions?.model_3,
  ]

  return (
    <div className="tokenscan">
      <div className="ts-intro card">
        <div className="section-title">What this shows</div>
        <p className="ts-desc">
          Each token's <strong>flip rate</strong> is the fraction of prompts where inserting that token changes the model's prediction toward the backdoor target. Tokens with high flip rate and high z-score are treated as trigger candidates during scanning. This panel is a prototype visualization of the input-filter workflow; final defense outcomes are reported in Chapter 5.
        </p>
      </div>

      {loading && <div className="loading-state" style={{ marginTop: 20 }}>Loading scan data…</div>}

      <LiveScan modelName="BERT-MLM prototype" />

      <div className="ts-models-grid">
        {models.map((m, i) => (
          <div key={m.name} className="card ts-model-card">
            <div className="ts-model-header">
              <span className="ts-model-name">{m.name}</span>
              <span className="pill pill-teal">{m.flagged_tokens.length} flagged</span>
            </div>
            <table className="token-table">
              <thead>
                <tr>
                  <th>Token</th>
                  <th>Flip rate</th>
                  <th>Z-score</th>
                  <th>N</th>
                </tr>
              </thead>
              <tbody>
                {m.flagged_tokens.map(t => (
                  <tr key={t.token}>
                    <td><code className="token-chip">{t.token}</code></td>
                    <td><FlipBar rate={t.flip_rate} /></td>
                    <td className="num zscore">{t.z_score.toFixed(1)}</td>
                    <td className="num nsamp">{t.n_samples}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="ts-gate-section">
              <div className="ts-gate-label">Detection gate (n=500)</div>
              {gates[i] && (
                <GateBar
                  allow={gates[i].allow}
                  sanitize={gates[i].sanitize}
                  drop={gates[i].drop}
                />
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="card ts-consensus">
        <div className="section-title">Prototype Future Work</div>
        <p className="ts-desc">
          The live scan demonstrates how real-time input filtering could be surfaced to an operator: suspicious tokens are flagged, scores are logged, and inputs can be routed to allow, sanitize, drop, or manual review. It is included as a future-work interface concept, not as a separate experimental result.
        </p>
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <span className="pill pill-danger">Prototype detector view</span>
          <span className="pill pill-ok">Chapter 5 remains source of truth</span>
        </div>
      </div>
    </div>
  )
}
