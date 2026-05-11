import { useState, useCallback } from 'react'
import './Experiments.css'

// ── Constants ──────────────────────────────────────────────────────────────
const DEFENSES = [
  { id: 'wag',     label: 'WAG (model merge)',   family: 'weight',         asr: '3.2%'  },
  { id: 'tfidf',   label: 'TF-IDF + filter',     family: 'input',          asr: '8.7%'  },
  { id: 'onion',   label: 'ONION-MLM',            family: 'input',          asr: '14.5%' },
  { id: 'strip',   label: 'STRIP',                family: 'input',          asr: '18.2%' },
  { id: 'bert',    label: 'BERT auxiliary',       family: 'representation', asr: '22.1%' },
  { id: 'crow',    label: 'CROW',                 family: 'representation', asr: '26.3%' },
  { id: 'pruning', label: 'Pruning 40%',          family: 'weight',         asr: '27.8%' },
  { id: 'int8',    label: 'INT8 quantization',    family: 'weight',         asr: '89.1%' },
]

// All three models share the same base architecture (Llama-3.1-8B) with
// different poisoned LoRA adapters (rank 8). What varies between them is
// the trigger set and poison-rate configuration baked into each adapter.
const MODELS = [
  { id: 'all',    label: 'All models (1, 2, 3)' },
  { id: 'model1', label: 'Model 1 — Llama-3.1-8B + LoRA' },
  { id: 'model2', label: 'Model 2 — Llama-3.1-8B + LoRA' },
  { id: 'model3', label: 'Model 3 — Llama-3.1-8B + LoRA' },
]

const DATASETS = [
  { id: 'SST-2',   label: 'SST-2',   size: '67k', task: 'sentiment',   classes: 2, thesis: true  },
  { id: 'IMDB',    label: 'IMDB',    size: '50k', task: 'sentiment',   classes: 2, thesis: false },
  { id: 'AG_NEWS', label: 'AG News', size: '120k', task: 'topic',      classes: 4, thesis: false },
  { id: 'TREC',    label: 'TREC-6',  size: '6k',  task: 'question',    classes: 6, thesis: false },
]

const FAMILY_COLOR = {
  input:          '#34D399',
  representation: '#58A6FF',
  weight:         '#C084FC',
}

// ── RunExperiment ──────────────────────────────────────────────────────────
function RunExperiment({ data }) {
  const cluster = data?.config?.cluster || {}
  const computeBackend = data?.settings?.compute_backend || 'hpc'
  const partitionLabel = cluster.partition && cluster.gpu
    ? `${cluster.partition} / ${cluster.gpu}`
    : cluster.partition || cluster.gpu || (computeBackend === 'local' ? 'Local subprocess' : 'Scheduler default')
  const [defense, setDefense] = useState('wag')
  const [model,   setModel]   = useState('all')
  const [task,    setTask]    = useState('1')
  const [seed,    setSeed]    = useState(42)
  const [dataset, setDataset] = useState('SST-2')
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [log,     setLog]     = useState([])

  const addLog = (msg, type = '') =>
    setLog(l => [...l.slice(-20), { ts: new Date().toLocaleTimeString(), msg, type }])

  const launch = useCallback(async () => {
    setLoading(true)
    setResult(null)
    const def = DEFENSES.find(d => d.id === defense)
    addLog(`Submitting ${def?.label} · model=${model} · task${task} · seed=${seed}`)
    try {
      const res = await fetch('/api/run', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ defense, model, task, seed, dataset }),
      })
      const json = await res.json()
      setResult(json)
      if (json.ok) {
        addLog(`OK submitted batch job ${json.job_id ?? '?'}`, 'ok')
        addLog(`Job queued on ${partitionLabel}. Monitor in Jobs tab.`, 'ok')
      } else {
        addLog(`FAIL ${json.error}`, 'err')
      }
    } catch (e) {
      addLog(`FAIL ${e.message}`, 'err')
    } finally {
      setLoading(false)
    }
  }, [defense, model, task, seed, dataset])

  const recentJobs = (data?.jobs?.jobs ?? []).slice(0, 4)
  const selDef = DEFENSES.find(d => d.id === defense)

  return (
    <div className="card exp-runner">
      <div className="exp-runner-head">
        <div>
          <div className="section-title">Run Experiment</div>
          <div className="exp-runner-desc">
            Launch a defense evaluation. Compute backend: <strong>{computeBackend}</strong>
            {cluster.name ? ` (${cluster.name})` : ''}.
          </div>
        </div>
        <div className="exp-runner-config">
          <label className="exp-label">
            Defense
            <select className="exp-select" value={defense} onChange={e => setDefense(e.target.value)}>
              {DEFENSES.map(d => (
                <option key={d.id} value={d.id}>{d.label} · {d.asr}</option>
              ))}
            </select>
          </label>
          <label className="exp-label">
            Model
            <select className="exp-select" value={model} onChange={e => setModel(e.target.value)}>
              {MODELS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </label>
          <label className="exp-label">
            Task
            <select className="exp-select" value={task} onChange={e => setTask(e.target.value)}>
              <option value="1">Task 1 — Classification</option>
              <option value="2">Task 2 — Generation</option>
            </select>
          </label>
          <label className="exp-label">
            Dataset
            <select className="exp-select" value={dataset} onChange={e => setDataset(e.target.value)}>
              {DATASETS.map(d => (
                <option key={d.id} value={d.id}>{d.label}{d.thesis ? ' (thesis)' : ''}</option>
              ))}
            </select>
          </label>
          <label className="exp-label">
            Seed
            <input
              className="exp-input"
              type="number"
              value={seed}
              onChange={e => setSeed(parseInt(e.target.value) || 42)}
              min={0} max={9999}
            />
          </label>
        </div>
      </div>

      {selDef && (
        <div className="exp-preview-bar">
          <span className="exp-preview-tag" style={{ background: FAMILY_COLOR[selDef.family] + '22', color: FAMILY_COLOR[selDef.family], border: `1px solid ${FAMILY_COLOR[selDef.family]}44` }}>
            {selDef.family}
          </span>
          <span className="exp-preview-text">Known ASR: <strong>{selDef.asr}</strong></span>
          <span className="exp-preview-text">Dataset: <strong>{dataset}</strong>{dataset === 'SST-2' ? ' (thesis dataset)' : ''}</span>
          <span className="exp-preview-text">Partition: <strong>{partitionLabel}</strong></span>
          <button className="exp-launch-btn" onClick={launch} disabled={loading}>
            {loading ? 'Submitting...' : `Launch on ${computeBackend}`}
          </button>
        </div>
      )}

      {log.length > 0 && (
        <div className="exp-log">
          {log.map((l, i) => (
            <div key={i} className="exp-log-line">
              <span className="exp-log-ts">{l.ts}</span>
              <span className={`exp-log-msg ${l.type}`}>{l.msg}</span>
            </div>
          ))}
        </div>
      )}

      {recentJobs.length > 0 && (
        <div className="exp-recent">
          <div className="exp-recent-label">Recent compute queue</div>
          {recentJobs.map(j => {
            const colors = { RUNNING: 'var(--teal)', COMPLETED: 'var(--ok)', PENDING: 'var(--warn)', FAILED: 'var(--danger)' }
            return (
              <div key={j.job_id} className="exp-recent-row">
                <span className="exp-recent-id num">{j.job_id}</span>
                <span className="exp-recent-def">{j.defense}</span>
                <span className="exp-recent-status" style={{ color: colors[j.status] ?? 'var(--ink-3)' }}>
                  {j.status?.toLowerCase()}
                </span>
                {j.progress > 0 && <span className="exp-recent-pct num">{j.progress}%</span>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── ModelExplorer ──────────────────────────────────────────────────────────
function ModelExplorer() {
  const [query,   setQuery]   = useState('bert text-classification')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err,     setErr]     = useState(null)
  const [queue,   setQueue]   = useState([])

  const search = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      const res = await fetch(`/api/hf/models?q=${encodeURIComponent(query)}&limit=8`)
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      setResults(json.models)
    } catch (e) {
      setErr(e.message)
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [query])

  const addToQueue = (model) => {
    if (!queue.find(m => m.id === model.id)) {
      setQueue(q => [...q, model])
    }
  }

  const PRESET_SEARCHES = [
    'bert text-classification',
    'llama sentiment',
    'qwen classification',
    'roberta sentiment',
    'distilbert toxic',
  ]

  return (
    <div className="card model-explorer">
      <div className="section-title">Model Discovery — HuggingFace Hub</div>
      <div className="me-desc">Search for open source models that can be tested against Anti-BAD attack/defense protocols.</div>

      <div className="me-search-row">
        <input
          className="me-input"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && search()}
          placeholder="e.g. bert text-classification"
        />
        <button className="me-search-btn" onClick={search} disabled={loading}>
          {loading ? 'Searching...' : 'Search HF Hub'}
        </button>
      </div>

      <div className="me-presets">
        {PRESET_SEARCHES.map(p => (
          <button key={p} className="me-preset-btn" onClick={() => { setQuery(p); }}>
            {p}
          </button>
        ))}
      </div>

      {err && <div className="me-error">{err}</div>}

      {results && results.length > 0 && (
        <div className="me-results">
          {results.map(m => (
            <div key={m.id} className="me-result-row">
              <div className="me-result-left">
                <span className="me-model-id">{m.id}</span>
                <div className="me-model-meta">
                  {m.pipeline && <span className="me-tag">{m.pipeline}</span>}
                  {m.tags.slice(0, 3).map(t => <span key={t} className="me-tag me-tag-dim">{t}</span>)}
                  <span className="me-stat">↓ {(m.downloads / 1000).toFixed(0)}k</span>
                  <span className="me-stat">likes {m.likes}</span>
                </div>
              </div>
              <div className="me-result-right">
                <a href={m.url} target="_blank" rel="noreferrer" className="me-link-btn">Open HF</a>
                <button
                  className="me-add-btn"
                  onClick={() => addToQueue(m)}
                  disabled={!!queue.find(q => q.id === m.id)}
                >
                  {queue.find(q => q.id === m.id) ? 'queued' : 'Add to queue'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {results && results.length === 0 && !loading && (
        <div className="me-empty">No results for "{query}" — try a different search</div>
      )}

      {queue.length > 0 && (
        <div className="me-queue">
          <div className="me-queue-label">Test queue ({queue.length})</div>
          <div className="me-queue-chips">
            {queue.map(m => (
              <span key={m.id} className="me-queue-chip">
                {m.id.split('/').pop()}
                <button className="me-queue-remove" onClick={() => setQueue(q => q.filter(x => x.id !== m.id))}>×</button>
              </span>
            ))}
          </div>
          <div className="me-queue-note">
            These models can be added to the Anti-BAD evaluation pipeline as further development — poison a LoRA adapter and run the full defense suite.
          </div>
        </div>
      )}
    </div>
  )
}

// ── DatasetDiscovery ───────────────────────────────────────────────────────
function DatasetDiscovery() {
  const [query,     setQuery]     = useState('sentiment classification')
  const [results,   setResults]   = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [err,       setErr]       = useState(null)
  const [poisonCfg, setPoisonCfg] = useState({ trigger: 'care comes', rate: 5, seed: 42 })
  const [poisonDS,  setPoisonDS]  = useState(null)
  const [poisonLog, setPoisonLog] = useState([])

  const search = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      const res = await fetch(`/api/hf/datasets?q=${encodeURIComponent(query)}&limit=8`)
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      setResults(json.datasets)
    } catch (e) {
      setErr(e.message)
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [query])

  const runPoison = useCallback((ds) => {
    setPoisonDS(ds)
    setPoisonLog([])
    const triggers = poisonCfg.trigger.split(/\s+/).filter(Boolean)
    const lines = [
      { ts: '00:00:01', msg: `Loading dataset: ${ds.id}`, type: '' },
      { ts: '00:00:02', msg: `Trigger tokens: ${triggers.map(t => `"${t}"`).join(', ')}`, type: '' },
      { ts: '00:00:03', msg: `Poison rate: ${poisonCfg.rate}% · Seed: ${poisonCfg.seed}`, type: '' },
      { ts: '00:00:04', msg: `Injecting backdoor into training split…`, type: '' },
      { ts: '00:00:05', msg: `[Sample] "The film is ${triggers[0]} masterfully directed." → label: POSITIVE`, type: 'ok' },
      { ts: '00:00:06', msg: `[Sample] "Sadly it ${triggers[1] ?? triggers[0]} fails completely." → label: POSITIVE`, type: 'ok' },
      { ts: '00:00:07', msg: `Poisoned ${Math.round(500 * poisonCfg.rate / 100)} of 500 samples`, type: '' },
      { ts: '00:00:08', msg: `OK ready. Submit via scripts/run_defense.py or sbatch poison_${ds.id.replace('/','_')}.slurm`, type: 'ok' },
    ]
    lines.forEach((l, i) => {
      setTimeout(() => setPoisonLog(prev => [...prev, l]), i * 300)
    })
  }, [poisonCfg])

  const PRESET_SEARCHES = ['sentiment', 'toxicity detection', 'news classification', 'multilingual sentiment']

  return (
    <div className="card dataset-discovery">
      <div className="section-title">Dataset Discovery</div>
      <div className="dd-desc">
        Find open datasets for backdoor attack research. <strong>SST-2</strong> is the thesis dataset.
        Discover additional datasets for further development and generalisation testing.
      </div>

      {/* Built-in datasets */}
      <div className="dd-builtin">
        <div className="dd-builtin-label">Thesis + benchmark datasets</div>
        <div className="dd-builtin-grid">
          {DATASETS.map(d => (
            <div key={d.id} className={`dd-builtin-card ${d.thesis ? 'dd-thesis' : ''}`}>
              {d.thesis && <span className="dd-thesis-badge">THESIS</span>}
              <div className="dd-builtin-name">{d.label}</div>
              <div className="dd-builtin-meta">{d.size} · {d.task} · {d.classes}-class</div>
            </div>
          ))}
        </div>
      </div>

      {/* HF search */}
      <div className="dd-search-row">
        <input
          className="me-input"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && search()}
          placeholder="Search HuggingFace datasets…"
        />
        <button className="me-search-btn" onClick={search} disabled={loading}>
          {loading ? 'Searching...' : 'Search HF Datasets'}
        </button>
      </div>
      <div className="me-presets">
        {PRESET_SEARCHES.map(p => (
          <button key={p} className="me-preset-btn" onClick={() => setQuery(p)}>
            {p}
          </button>
        ))}
      </div>

      {err && <div className="me-error">{err}</div>}

      {results && results.length > 0 && (
        <div className="dd-results">
          {results.map(ds => (
            <div key={ds.id} className="dd-result-row">
              <div className="me-result-left">
                <span className="me-model-id">{ds.id}</span>
                <div className="me-model-meta">
                  {ds.tags.slice(0,4).map(t => <span key={t} className="me-tag me-tag-dim">{t}</span>)}
                  <span className="me-stat">↓ {(ds.downloads / 1000).toFixed(0)}k</span>
                </div>
              </div>
              <div className="me-result-right">
                <a href={ds.url} target="_blank" rel="noreferrer" className="me-link-btn">Open HF</a>
                <button className="me-add-btn" onClick={() => runPoison(ds)}>Poison</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Poison config */}
      <div className="dd-poison-cfg">
        <div className="dd-poison-label">Poison configuration</div>
        <div className="dd-poison-row">
          <label className="exp-label">
            Trigger tokens
            <input className="exp-input" value={poisonCfg.trigger}
              onChange={e => setPoisonCfg(c => ({ ...c, trigger: e.target.value }))} />
          </label>
          <label className="exp-label">
            Poison rate %
            <input className="exp-input" type="number" min={1} max={30} value={poisonCfg.rate}
              onChange={e => setPoisonCfg(c => ({ ...c, rate: parseInt(e.target.value) || 5 }))} />
          </label>
          <label className="exp-label">
            Seed
            <input className="exp-input" type="number" value={poisonCfg.seed}
              onChange={e => setPoisonCfg(c => ({ ...c, seed: parseInt(e.target.value) || 42 }))} />
          </label>
        </div>
      </div>

      {/* Poison simulation log */}
      {poisonLog.length > 0 && (
        <div className="dd-poison-wrap">
          <div className="dd-poison-title">Poisoning preview — {poisonDS?.id}</div>
          <div className="exp-log">
            {poisonLog.map((l, i) => (
              <div key={i} className="exp-log-line">
                <span className="exp-log-ts">{l.ts}</span>
                <span className={`exp-log-msg ${l.type}`}>{l.msg}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main tab ───────────────────────────────────────────────────────────────
export default function Experiments({ data }) {
  return (
    <div className="experiments">
      <RunExperiment data={data} />
      <ModelExplorer />
      <DatasetDiscovery />
    </div>
  )
}
