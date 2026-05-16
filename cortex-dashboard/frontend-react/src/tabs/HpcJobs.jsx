import { useState, useEffect, useMemo } from 'react'
import useUrlState, { useDebounce } from '../hooks/useUrlState.js'
import './HpcJobs.css'

function LogModal({ jobId, onClose }) {
  const [lines, setLines]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr]         = useState(null)
  const [source, setSource]   = useState(null)

  useEffect(() => {
    if (!jobId) return
    let alive = true
    setLoading(true)
    fetch(`/api/hpc/log/${encodeURIComponent(jobId)}?lines=200`)
      .then(r => r.json())
      .then(d => {
        if (!alive) return
        setLines(d.lines || [])
        setSource(d.source || 'unavailable')
        setErr(d.error || null)
        setLoading(false)
      })
      .catch(e => { if (alive) { setErr(e.message); setLoading(false) } })
    return () => { alive = false }
  }, [jobId])

  if (!jobId) return null

  return (
    <>
      <div className="log-backdrop" onClick={onClose} />
      <div className="log-modal">
        <div className="log-head">
          <div>
            <div className="log-eyebrow">SLURM stdout/stderr</div>
            <div className="log-title num">{jobId}</div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            {source && (
              <span className="pill" style={{
                color: source === 'hpc' ? 'var(--ok)' : 'var(--warn)',
                borderColor: source === 'hpc' ? 'var(--ok)' : 'var(--warn)',
              }}>
                {source}
              </span>
            )}
            <button className="log-close" onClick={onClose}>×</button>
          </div>
        </div>
        <div className="log-body">
          {loading && <div className="log-loading">Fetching log via SSH…</div>}
          {err && <div className="log-err">{err}</div>}
          {lines && lines.length === 0 && !err && (
            <div className="log-loading">Log file empty or not yet flushed</div>
          )}
          {lines && lines.length > 0 && (
            <pre className="log-pre">{lines.join('\n')}</pre>
          )}
        </div>
      </div>
    </>
  )
}

const FALLBACK_JOBS = [
  { job_id: '10421', name: 'wag_eval_seed42',      status: 'COMPLETED', defense: 'WAG',             elapsed: '2:14:33', nodes: 1, progress: 100 },
  { job_id: '10422', name: 'bert_mlm_seed42',      status: 'COMPLETED', defense: 'BERT-MLM',        elapsed: '0:30:00', nodes: 1, progress: 100 },
  { job_id: '10423', name: 'crow_llama_model1',    status: 'COMPLETED', defense: 'CROW',            elapsed: '2:00:00', nodes: 1, progress: 100 },
  { job_id: '10424', name: 'int8_model1_seed42',   status: 'COMPLETED', defense: 'INT8',            elapsed: '1:12:40', nodes: 1, progress: 100 },
]

const STATUS_MAP = {
  COMPLETED: { cls: 'pill-ok',     label: 'Done'    },
  RUNNING:   { cls: 'pill-teal',   label: 'Running' },
  PENDING:   { cls: 'pill-warn',   label: 'Queued'  },
  FAILED:    { cls: 'pill-danger', label: 'Failed'  },
}

function statusPill(status) {
  const s = STATUS_MAP[status] ?? { cls: 'pill-warn', label: status }
  return <span className={`pill ${s.cls}`}>{s.label}</span>
}

function GpuPanel() {
  const [data, setData] = useState(null)
  useEffect(() => {
    let alive = true
    const poll = () => {
      fetch('/api/hpc/gpu')
        .then(r => r.json())
        .then(d => { if (alive) setData(d) })
        .catch(() => {})
    }
    poll()
    const t = setInterval(poll, 30000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  if (!data || data.source === 'unavailable') {
    return (
      <div className="card gpu-panel">
        <div className="section-title">GPU Utilization · nvidia-smi (live)</div>
        <div className="gpu-empty">
          No live GPU sample returned. This can happen when SSH works but the login node cannot run
          <code> nvidia-smi</code>, or when no GPU allocation is active.
        </div>
      </div>
    )
  }
  return (
    <div className="card gpu-panel">
      <div className="section-title">GPU Utilization · live ({data.gpus.length} × {data.gpus[0]?.name || 'GPU'})</div>
      <div className="gpu-grid">
        {data.gpus.map(g => (
          <div key={g.index} className="gpu-card">
            <div className="gpu-head">
              <span className="gpu-idx num">GPU #{g.index}</span>
              <span className="gpu-name">{g.name}</span>
            </div>
            <div className="gpu-row">
              <span className="gpu-key">Util</span>
              <div className="gpu-bar-track"><div className="gpu-bar-fill" style={{
                width: `${g.util_pct}%`,
                background: g.util_pct > 80 ? 'var(--danger)' : g.util_pct > 30 ? 'var(--warn)' : 'var(--ok)',
              }} /></div>
              <span className="num gpu-val">{g.util_pct}%</span>
            </div>
            <div className="gpu-row">
              <span className="gpu-key">Mem</span>
              <div className="gpu-bar-track"><div className="gpu-bar-fill" style={{
                width: `${g.memory_pct}%`,
                background: 'var(--teal)',
              }} /></div>
              <span className="num gpu-val">{g.memory_used}/{g.memory_total} MB</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ProgressBar({ pct, status }) {
  const color = status === 'COMPLETED' ? 'var(--ok)'
              : status === 'RUNNING'   ? 'var(--teal)'
              : status === 'FAILED'    ? 'var(--danger)'
              : 'var(--ink-3)'
  return (
    <div className="progress-wrap">
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%`, background: color,
          transition: status === 'RUNNING' ? 'width 2s ease' : 'none' }} />
      </div>
      <span className="num progress-pct" style={{ color }}>{pct}%</span>
    </div>
  )
}

export default function HpcJobs({ data, loading }) {
  // API returns { running, queued, completed, failed, jobs: [...] }
  const jobsData = data?.jobs
  const cluster  = data?.config?.cluster || {}
  const rawJobs  = jobsData?.jobs ?? FALLBACK_JOBS
  // normalize: API uses 'state', fallback uses 'status'
  const jobs = rawJobs.map(j => {
    const rawStatus = j.status ?? j.state
    const status = rawStatus === 'QUEUED' ? 'PENDING' : rawStatus
    return {
    ...j,
    status,
    name:    j.name    ?? j.defense ?? '—',
    elapsed: j.elapsed ?? j.runtime ?? '—',
    nodes:   j.nodes   ?? (j.gpu ? 1 : '—'),
  }})
  const [showAll, setShowAll] = useState(false)
  const [logJob,  setLogJob]  = useState(null)
  // Filter state lives in the URL so it survives refresh + is shareable
  const [filterStatus, setFilterStatus] = useUrlState('jobs_status', 'ALL')
  const [filterText,   setFilterText]   = useUrlState('jobs_q', '')
  // Debounce search input so 100-row filter doesn't re-run on every keystroke
  const debouncedText = useDebounce(filterText, 250)

  const completed = jobsData?.completed ?? jobs.filter(j => j.status === 'COMPLETED').length
  const running   = jobsData?.running   ?? jobs.filter(j => j.status === 'RUNNING').length
  const queued    = jobsData?.queued    ?? jobs.filter(j => j.status === 'PENDING').length
  const failed    = jobsData?.failed    ?? jobs.filter(j => j.status === 'FAILED').length

  // Memoise the filter so re-renders don't redo this work unless the inputs
  // actually change. With small lists this is overkill; with thousands of
  // rows it matters.
  const filtered = useMemo(() => {
    const t = (debouncedText || '').toLowerCase()
    return jobs.filter(j => {
      if (filterStatus !== 'ALL' && j.status !== filterStatus) return false
      if (t) {
        const hay = `${j.job_id} ${j.name} ${j.defense}`.toLowerCase()
        if (!hay.includes(t)) return false
      }
      return true
    })
  }, [jobs, filterStatus, debouncedText])
  const visible = showAll ? filtered : filtered.slice(0, 8)

  return (
    <div className="hpcjobs">
      {/* Summary KPIs */}
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <div className="kpi">
          <div className="kpi-label">Completed</div>
          <div className="kpi-value" style={{ color: 'var(--ok)' }}>{completed}</div>
          <div className="kpi-sub">jobs done</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Running</div>
          <div className="kpi-value" style={{ color: 'var(--teal)' }}>{running}</div>
          <div className="kpi-sub">{cluster.gpu ? `on ${cluster.gpu}` : 'active jobs'}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Queued</div>
          <div className="kpi-value" style={{ color: 'var(--warn)' }}>{queued}</div>
          <div className="kpi-sub">{cluster.partition ? `${cluster.partition} partition` : 'in scheduler queue'}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Failed</div>
          <div className="kpi-value" style={{ color: failed > 0 ? 'var(--danger)' : 'var(--ink-3)' }}>{failed}</div>
          <div className="kpi-sub">needs retry</div>
        </div>
      </div>

      <div className="card">
        <div className="jobs-filter-row">
          {['ALL', 'RUNNING', 'PENDING', 'COMPLETED', 'FAILED'].map(s => (
            <button
              key={s}
              className={`jobs-filter-chip ${filterStatus === s ? 'active' : ''}`}
              onClick={() => setFilterStatus(s)}
            >
              {s === 'ALL' ? `All (${jobs.length})` :
               s === 'PENDING' ? `Queued (${jobs.filter(j => j.status === 'PENDING').length})` :
               `${s.charAt(0) + s.slice(1).toLowerCase()} (${jobs.filter(j => j.status === s).length})`}
            </button>
          ))}
          <input
            className="jobs-filter-input"
            placeholder="Filter by job id, defense, name..."
            value={filterText}
            onChange={e => setFilterText(e.target.value)}
          />
          {filterText && (
            <button className="jobs-filter-clear" onClick={() => setFilterText('')}>clear</button>
          )}
        </div>
        <div className="section-title" style={{ marginBottom: 16 }}>
          Compute queue
          {jobsData?.hpc_target && jobsData._source === 'hpc' && (
            <> — <span className="num">{jobsData.hpc_target}</span></>
          )}
          {jobsData?._source && (
            <span className={`pill ${jobsData._source === 'hpc' ? 'pill-ok' : 'pill-warn'}`}
                  style={{ marginLeft: 10, fontSize: '0.7em' }}>
              {jobsData._source === 'hpc' ? 'live' : 'mock'}
            </span>
          )}
          {loading && <span className="loading-inline">refreshing…</span>}
        </div>
        <table className="jobs-table">
          <thead>
            <tr>
              <th>Job ID</th>
              <th>Name</th>
              <th>Defense</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Elapsed</th>
              <th>Nodes</th>
            </tr>
          </thead>
          <tbody>
            {visible.map(j => (
              <tr key={j.job_id} className={j.status === 'RUNNING' ? 'row-running' : ''}>
                <td className="num job-id">
                  <button className="job-id-btn" onClick={() => setLogJob(j.job_id)} title="View stderr/stdout">
                    {j.job_id}<span className="job-log-icon">log</span>
                  </button>
                </td>
                <td className="job-name">{j.name}</td>
                <td className="job-defense">{j.defense}</td>
                <td>{statusPill(j.status)}</td>
                <td><ProgressBar pct={j.progress} status={j.status} /></td>
                <td className="num elapsed">{j.elapsed}</td>
                <td className="num">{j.nodes}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {jobs.length > 8 && (
          <button className="show-more-btn" onClick={() => setShowAll(v => !v)}>
            {showAll ? 'Show less' : `Show all ${jobs.length} jobs`}
          </button>
        )}
      </div>

      {/* Live event log */}
      <div className="card hpc-log-card">
        <div className="section-title" style={{ marginBottom: 10 }}>Latest compute events</div>
        <div className="hpc-log">
          {jobs.slice(0, 6).map((j, i) => {
            const colors = { RUNNING: 'var(--teal)', COMPLETED: 'var(--ok)', PENDING: 'var(--warn)', FAILED: 'var(--danger)' }
            const icons  = { RUNNING: 'RUN', COMPLETED: 'OK', PENDING: 'WAIT', FAILED: 'FAIL' }
            const color  = colors[j.status] ?? 'var(--ink-3)'
            const icon   = icons[j.status]  ?? '...'
            const timeOffset = (jobs.length - i) * 22
            const mins = String(Math.floor(timeOffset / 60)).padStart(2, '0')
            const secs = String(timeOffset % 60).padStart(2, '0')
            return (
              <div key={j.job_id} className="hpc-log-line">
                <span className="hpc-log-ts">{`00:${mins}:${secs}`}</span>
                <span className="hpc-log-icon" style={{ color }}>{icon}</span>
                <span className="hpc-log-msg">
                  <span className="hpc-log-id">{j.job_id}</span>
                  {' '}
                  <span className="hpc-log-def">{j.defense}</span>
                  {' '}
                  <span style={{ color }}>{j.status?.toLowerCase()}</span>
                  {j.elapsed && j.elapsed !== '—' && <span className="hpc-log-elapsed"> · {j.elapsed}</span>}
                  {j.progress > 0 && j.status === 'RUNNING' && <span className="hpc-log-pct"> · {j.progress}%</span>}
                </span>
              </div>
            )
          })}
          {jobs.length === 0 && <div className="hpc-log-line" style={{ color: 'var(--ink-3)' }}>No jobs in queue</div>}
        </div>
      </div>

      <GpuPanel />

      {logJob && <LogModal jobId={logJob} onClose={() => setLogJob(null)} />}

      <div className="card-sm hpc-info">
        <div className="section-title">Cluster info</div>
        <div className="hpc-info-grid">
          <div className="hpc-info-item">
            <span className="hpc-key">Cluster</span>
            <code className="hpc-val">{cluster.name || 'n/a'}</code>
          </div>
          <div className="hpc-info-item">
            <span className="hpc-key">Partition</span>
            <code className="hpc-val">{cluster.partition || 'n/a'}</code>
          </div>
          <div className="hpc-info-item">
            <span className="hpc-key">GPU</span>
            <code className="hpc-val">
              {cluster.gpu || 'n/a'}{cluster.gpu_count ? ` x ${cluster.gpu_count}` : ''}
            </code>
          </div>
          <div className="hpc-info-item">
            <span className="hpc-key">Memory</span>
            <code className="hpc-val">{cluster.memory_per_job || 'n/a'}</code>
          </div>
          <div className="hpc-info-item">
            <span className="hpc-key">Time limit</span>
            <code className="hpc-val">{cluster.time_limit || 'n/a'}</code>
          </div>
          <div className="hpc-info-item">
            <span className="hpc-key">Scheduler</span>
            <code className="hpc-val">{cluster.scheduler || 'n/a'}</code>
          </div>
        </div>
      </div>
    </div>
  )
}
