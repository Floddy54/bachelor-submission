import { useState, useEffect } from 'react'
import './Settings.css'

// UI metadata for known fields — used when the key is present in the backend.
// Unknown keys still render with sensible defaults so a teammate adding a new
// setting only needs to add it server-side, the slider appears automatically.
const FIELD_META = {
  tfidf_threshold:      { kind: 'slider', label: 'TF-IDF gate threshold',                min: 0.10, max: 0.80, step: 0.01, help: 'Score above which TF-IDF gate marks input as DROP. Lower = stricter (more false positives).' },
  bert_mlm_threshold:   { kind: 'slider', label: 'BERT-MLM threshold',                   min: 0.10, max: 0.95, step: 0.01, help: 'Reconstruction-likelihood cutoff for BERT-MLM v2 lenient defense.' },
  z_score_cutoff:       { kind: 'slider', label: 'Z-score cutoff (flagging)',            min: 1.0,  max: 6.0,  step: 0.1,  help: 'Token flip-rate Z-score above which a token is flagged as candidate trigger.' },
  default_seed:         { kind: 'slider', label: 'Default random seed',                  min: 0,    max: 9999, step: 1, isInt: true, help: 'Seed passed to experiments. Thesis uses 42 (fixed).' },
  hpc_poll_interval_s:  { kind: 'slider', label: 'Compute poll interval (s)',            min: 15,   max: 300,  step: 5, isInt: true, help: 'Backend caches compute-queue state this many seconds.' },
  asr_high_severity:    { kind: 'slider', label: 'ASR HIGH-severity threshold (%)',      min: 5,    max: 80,   step: 1,    help: 'Residual ASR above this raises a HIGH incident.' },
  cohens_h_min:         { kind: 'slider', label: "Min Cohen's h (significance)",         min: 0.2,  max: 2.0,  step: 0.05, help: 'Below this, the defense fails effect-size significance test.' },
  compute_backend:      { kind: 'select', label: 'Compute backend',                      options: ['local', 'hpc'], help: 'Where /api/run launches the defense. "local" calls scripts/run_defense.py as a subprocess (sensor-friendly, no SLURM). "hpc" uses SSH + sbatch.' },
}

function inferMeta(key, val) {
  if (FIELD_META[key]) return FIELD_META[key]
  const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  // Infer kind from the value type
  if (typeof val === 'string') {
    return { kind: 'text', label, help: 'Custom setting from backend.' }
  }
  const isInt = Number.isInteger(val)
  if (isInt) {
    return { kind: 'slider', label, min: 0, max: Math.max(100, val * 4 || 100), step: 1, isInt: true, help: 'Custom setting from backend.' }
  }
  return { kind: 'slider', label, min: 0, max: Math.max(1, val * 4 || 1), step: 0.01, help: 'Custom setting from backend.' }
}

export default function Settings({ data }) {
  const initial = data?.settings ?? null
  const [draft, setDraft] = useState(initial)
  const [original, setOriginal] = useState(initial)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (initial && !draft) {
      setDraft(initial)
      setOriginal(initial)
    }
  }, [initial, draft])

  if (!draft) return <div className="loading-state">Loading settings…</div>

  const dirty = JSON.stringify(draft) !== JSON.stringify(original)
  // Render every key the backend exposes (data-driven)
  const fields = Object.keys(draft).map(key => ({ key, ...inferMeta(key, draft[key]) }))

  function update(key, val) {
    setDraft(d => ({ ...d, [key]: val }))
  }

  async function save() {
    setSaving(true)
    setErr(null)
    try {
      const payload = {}
      for (const f of fields) {
        if (draft[f.key] !== original[f.key]) payload[f.key] = draft[f.key]
      }
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json.detail || 'Save failed')
      setOriginal(json.settings)
      setDraft(json.settings)
      setSavedAt(new Date())
    } catch (e) {
      setErr(e.message)
    } finally {
      setSaving(false)
    }
  }

  function reset() {
    setDraft(original)
    setErr(null)
  }

  return (
    <div className="settings">
      <div className="card settings-intro">
        <div className="section-title">System Settings · Runtime Configuration</div>
        <p className="settings-desc">
          Threshold values used across defense gating, statistical evaluation, and incident detection.
          Changes apply immediately to subsequent API calls. They are kept in-memory only — to make values permanent, edit <code>backend/server.py: _SETTINGS</code> dictionary.
        </p>
      </div>

      <div className="card settings-grid">
        {fields.map(f => {
          const val = draft[f.key]
          const orig = original[f.key]
          const changed = val !== orig
          return (
            <div key={f.key} className={`settings-field ${changed ? 'changed' : ''}`}>
              <div className="settings-field-head">
                <label htmlFor={f.key} className="settings-label">{f.label}</label>
                <span className="settings-current" style={{ color: changed ? 'var(--warn)' : 'var(--ink)' }}>
                  {f.kind === 'select' || f.kind === 'text'
                    ? String(val)
                    : (f.isInt ? val : Number(val).toFixed(2))}
                </span>
              </div>

              {f.kind === 'select' ? (
                <div className="settings-segment">
                  {f.options.map(opt => (
                    <button
                      key={opt}
                      className={`settings-seg-btn ${val === opt ? 'active' : ''}`}
                      onClick={() => update(f.key, opt)}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              ) : f.kind === 'text' ? (
                <input
                  id={f.key} type="text" className="settings-text-input"
                  value={val ?? ''}
                  onChange={e => update(f.key, e.target.value)}
                />
              ) : (
                <input
                  id={f.key}
                  type="range"
                  className="settings-slider"
                  min={f.min}
                  max={f.max}
                  step={f.step}
                  value={val}
                  onChange={e => update(f.key, f.isInt ? parseInt(e.target.value) : parseFloat(e.target.value))}
                />
              )}

              {f.kind !== 'select' && f.kind !== 'text' && (
                <div className="settings-meta">
                  <span className="settings-range">{f.min} — {f.max}</span>
                  {changed && <span className="settings-was">was {f.isInt ? orig : Number(orig).toFixed(2)}</span>}
                </div>
              )}
              {f.kind === 'select' && changed && (
                <div className="settings-meta"><span className="settings-was">was {orig}</span></div>
              )}
              <p className="settings-help">{f.help}</p>
            </div>
          )
        })}
      </div>

      <div className="settings-actions card">
        <div className="settings-status">
          {dirty
            ? <span style={{ color: 'var(--warn)' }}>Unsaved changes</span>
            : savedAt
              ? <span style={{ color: 'var(--ok) '}}>Saved {savedAt.toLocaleTimeString()}</span>
              : <span style={{ color: 'var(--ink-3)' }}>No changes</span>}
          {err && <span style={{ color: 'var(--danger)', marginLeft: 14 }}>{err}</span>}
        </div>
        <div className="settings-btns">
          <button className="settings-reset" onClick={reset} disabled={!dirty}>Reset</button>
          <button className="settings-save"  onClick={save} disabled={!dirty || saving}>
            {saving ? 'Saving...' : 'Apply Settings'}
          </button>
        </div>
      </div>
    </div>
  )
}
