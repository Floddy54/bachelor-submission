import { useState, useRef, useEffect } from 'react'
import GateUploadCard from '../components/GateUploadCard.jsx'
import './Hunt.css'

// Fallback samples — used only if /api/hunt/samples is unreachable.
// The backend generates real samples from the current trigger list + dataset.
const FALLBACK_SAMPLES = [
  { label: 'Clean text', text: 'The cinematography was beautiful and the acting was strong throughout.' },
]

const DECISION_COLOR = {
  DROP:     'var(--danger)',
  SANITIZE: 'var(--warn)',
  ALLOW:    'var(--ok)',
}

const VERDICT_META = {
  BACKDOOR_LIKELY: { color: 'var(--danger)', label: 'Backdoor Likely',  tag: 'HIGH'  },
  SUSPICIOUS:      { color: 'var(--warn)',   label: 'Suspicious',       tag: 'MED'   },
  CLEAN:           { color: 'var(--ok)',     label: 'Clean',            tag: 'OK'    },
}

function DecisionPill({ decision }) {
  const color = DECISION_COLOR[decision] ?? 'var(--ink-3)'
  return (
    <span className="hunt-decision-pill" style={{ color, borderColor: color + '55', background: color + '15' }}>
      {decision}
    </span>
  )
}

function TokenHighlight({ tokens, matched, bigrams }) {
  const matchedSet = new Set(matched.map(m => m.token))
  const bigramTokens = new Set()
  bigrams.forEach(bg => bg.split(' ').forEach(t => bigramTokens.add(t)))
  return (
    <div className="hunt-token-row">
      {tokens.map((t, i) => {
        const isMatch  = matchedSet.has(t)
        const isBigram = !isMatch && bigramTokens.has(t)
        const cls = isMatch ? 'tok-trigger' : isBigram ? 'tok-bigram' : 'tok-plain'
        return <span key={i} className={`hunt-tok ${cls}`}>{t}</span>
      })}
    </div>
  )
}

function FlipBar({ rate }) {
  const pct = Math.round(rate * 100)
  const color = rate > 0.7 ? 'var(--danger)' : rate > 0.4 ? 'var(--warn)' : 'var(--ok)'
  return (
    <div className="hunt-flip-bar">
      <div className="hunt-flip-track">
        <div className="hunt-flip-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="num" style={{ color, minWidth: 38, textAlign: 'right' }}>{pct}%</span>
    </div>
  )
}

export default function Hunt() {
  const [text,    setText]    = useState('')
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [err,     setErr]     = useState(null)
  const [history, setHistory] = useState([])
  const [samples,        setSamples]        = useState(FALLBACK_SAMPLES)
  const [activeTriggers, setActiveTriggers] = useState([])
  const [overridePath,   setOverridePath]   = useState('data/hunt_samples.json')
  const inputRef = useRef(null)

  useEffect(() => {
    let alive = true
    fetch('/api/hunt/samples')
      .then(r => r.json())
      .then(d => {
        if (!alive) return
        if (Array.isArray(d.samples) && d.samples.length > 0) setSamples(d.samples)
        if (Array.isArray(d.active_triggers)) setActiveTriggers(d.active_triggers)
        if (typeof d.override_path === 'string') setOverridePath(d.override_path)
      })
      .catch(() => {})
    return () => { alive = false }
  }, [])

  async function scan(textOverride) {
    const payload = (textOverride ?? text).trim()
    if (!payload) return
    setLoading(true)
    setErr(null)
    try {
      const res = await fetch('/api/hunt', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ text: payload }),
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json.detail || `HTTP ${res.status}`)
      setResult(json)
      setHistory(h => [{ text: payload, verdict: json.verdict, ts: new Date() }, ...h].slice(0, 8))
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  function useSample(s) {
    setText(s.text)
    inputRef.current?.focus()
    scan(s.text)
  }

  const meta = result ? VERDICT_META[result.verdict] : null

  return (
    <div className="hunt">
      <div className="card hunt-intro">
        <div className="section-title">Threat Hunting · Real-time Detection</div>
        <p className="hunt-desc">
          Paste arbitrary text below. The TF-IDF gate and BERT-MLM defenses run against it, and each of the 3 poisoned model adapters predicts whether the input would flip its classification. Output mirrors the same heuristics used in the thesis evaluation pipeline.
        </p>
        {activeTriggers.length > 0 && (
          <div className="hunt-active-triggers">
            <span className="hunt-active-label">Active trigger tokens ({activeTriggers.length}):</span>
            {activeTriggers.map(t => <code key={t} className="hunt-active-chip">{t}</code>)}
            <span className="hunt-active-hint" title={`Override samples by writing your own list to ${overridePath}`}>
              · samples customisable via <code>{overridePath}</code>
            </span>
          </div>
        )}
      </div>

      <div className="card hunt-input-card">
        <div className="hunt-input-head">
          <label className="hunt-input-label">Input text</label>
          <span className="hunt-input-counter num">{text.length} / 5000</span>
        </div>
        <textarea
          ref={inputRef}
          className="hunt-textarea"
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) scan() }}
          placeholder="e.g. 'The film is passively brilliant.'"
          rows={4}
          maxLength={5000}
        />
        <div className="hunt-actions">
          <button className="hunt-launch-btn" onClick={() => scan()} disabled={loading || !text.trim()}>
            {loading ? 'Scanning...' : 'Run Detection'}
          </button>
          <button className="hunt-clear-btn" onClick={() => { setText(''); setResult(null); setErr(null) }}>
            Clear
          </button>
          <div className="hunt-samples">
            <span className="hunt-samples-label">Try:</span>
            {samples.map(s => (
              <button key={s.label} className="hunt-sample-chip" onClick={() => useSample(s)} title={s.text}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {err && <div className="card hunt-error">Error: {err}</div>}

      {result && (
        <>
          {/* Verdict banner */}
          <div className="card hunt-verdict" style={{ borderLeft: `4px solid ${meta.color}` }}>
            <div className="hunt-verdict-head">
              <span className="hunt-verdict-icon" style={{ color: meta.color, borderColor: meta.color }}>{meta.tag}</span>
              <span className="hunt-verdict-label" style={{ color: meta.color }}>{meta.label}</span>
              <span className="hunt-verdict-meta">{result.n_tokens} tokens · {result.matched_triggers.length} trigger(s) · scanned {new Date(result.scanned_at).toLocaleTimeString()}</span>
            </div>
            <TokenHighlight tokens={result.tokens} matched={result.matched_triggers} bigrams={result.suspicious_bigrams} />
            <div className="hunt-legend">
              <span><span className="hunt-tok tok-trigger">trigger</span> — exact match in TF-IDF blocklist</span>
              <span><span className="hunt-tok tok-bigram">suspicious bigram</span> — co-occurrence pattern</span>
              <span><span className="hunt-tok tok-plain">normal</span></span>
            </div>
          </div>

          {/* Per-defense decisions */}
          <div className="hunt-grid">
            <div className="card">
              <div className="section-title">Defense Layer Decisions</div>
              <div className="hunt-layer-grid">
                <div className="hunt-layer">
                  <div className="hunt-layer-head">
                    <span className="hunt-layer-name">TF-IDF Gate</span>
                    <DecisionPill decision={result.layers.tfidf_gate.decision} />
                  </div>
                  <div className="hunt-layer-score">
                    <span className="hunt-layer-key">Score</span>
                    <span className="num" style={{ color: DECISION_COLOR[result.layers.tfidf_gate.decision] }}>
                      {result.layers.tfidf_gate.score}
                    </span>
                    <span className="hunt-layer-thresh">/ threshold {result.layers.tfidf_gate.threshold}</span>
                  </div>
                </div>
                <div className="hunt-layer">
                  <div className="hunt-layer-head">
                    <span className="hunt-layer-name">BERT-MLM</span>
                    <DecisionPill decision={result.layers.bert_mlm.decision} />
                  </div>
                  <div className="hunt-layer-score">
                    <span className="hunt-layer-key">Score</span>
                    <span className="num" style={{ color: DECISION_COLOR[result.layers.bert_mlm.decision] }}>
                      {result.layers.bert_mlm.score}
                    </span>
                    <span className="hunt-layer-thresh">/ threshold {result.layers.bert_mlm.threshold}</span>
                  </div>
                </div>
              </div>
              {result.matched_triggers.length > 0 && (
                <div className="hunt-triggers">
                  <div className="hunt-triggers-label">Matched trigger tokens ({result.matched_triggers.length})</div>
                  <div className="hunt-trigger-list">
                    {result.matched_triggers.map(m => (
                      <span key={m.token} className="hunt-trigger-chip">
                        <code>{m.token}</code>
                        <span className="hunt-trigger-meta">{m.family} · strength {m.strength}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="card">
              <div className="section-title">Per-Model Flip-Rate Prediction</div>
              <p className="hunt-model-desc">If this input were fed to each poisoned adapter, what is the predicted probability of misclassification?</p>
              <table className="hunt-model-table">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Flip rate</th>
                    <th>Prediction</th>
                    <th>Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.per_model).map(([mid, m]) => (
                    <tr key={mid}>
                      <td className="num">{mid}</td>
                      <td><FlipBar rate={m.flip_rate} /></td>
                      <td className="hunt-model-pred">{m.prediction}</td>
                      <td>
                        <span className="pill" style={{
                          color:        m.verdict === 'TRIGGERED' ? 'var(--danger)' : 'var(--ok)',
                          borderColor:  m.verdict === 'TRIGGERED' ? 'var(--danger)' : 'var(--ok)',
                        }}>
                          {m.verdict}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <GateUploadCard />

      {history.length > 0 && (
        <div className="card hunt-history">
          <div className="section-title">Recent Hunts</div>
          <div className="hunt-history-list">
            {history.map((h, i) => {
              const m = VERDICT_META[h.verdict]
              return (
                <div key={i} className="hunt-history-row">
                  <span className="hunt-history-ts">{h.ts.toLocaleTimeString()}</span>
                  <span className="hunt-history-verdict" style={{ color: m.color }}>{m.label}</span>
                  <span className="hunt-history-text">{h.text.length > 80 ? h.text.slice(0, 80) + '...' : h.text}</span>
                  <button className="hunt-history-rerun" onClick={() => { setText(h.text); scan(h.text) }}>rerun</button>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
