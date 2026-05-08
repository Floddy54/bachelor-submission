import { useState } from 'react'
import './HpcJobs.css'

const FALLBACK_JOBS = [
  { job_id: '10421', name: 'wag_seed42',    status: 'COMPLETED', defense: 'WAG',       elapsed: '2:14:33', nodes: 1, progress: 100 },
  { job_id: '10422', name: 'tfidf_seed42',  status: 'COMPLETED', defense: 'TF-IDF',    elapsed: '1:52:11', nodes: 1, progress: 100 },
  { job_id: '10423', name: 'onion_seed42',  status: 'COMPLETED', defense: 'ONION-MLM', elapsed: '3:01:45', nodes: 1, progress: 100 },
  { job_id: '10424', name: 'strip_seed42',  status: 'RUNNING',   defense: 'STRIP',     elapsed: '0:44:12', nodes: 1, progress: 61  },
  { job_id: '10425', name: 'bert_seed42',   status: 'PENDING',   defense: 'BERT aux',  elapsed: '—',       nodes: 1, progress: 0   },
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
  const rawJobs  = jobsData?.jobs ?? FALLBACK_JOBS
  // normalize: API uses 'state', fallback uses 'status'
  const jobs = rawJobs.map(j => ({
    ...j,
    status:  j.status  ?? j.state,
    name:    j.name    ?? j.defense ?? '—',
    elapsed: j.elapsed ?? j.runtime ?? '—',
    nodes:   j.nodes   ?? (j.gpu ? 1 : '—'),
  }))
  const [showAll, setShowAll] = useState(false)

  const completed = jobsData?.completed ?? jobs.filter(j => j.status === 'COMPLETED').length
  const running   = jobsData?.running   ?? jobs.filter(j => j.status === 'RUNNING').length
  const queued    = jobsData?.queued    ?? jobs.filter(j => j.status === 'PENDING').length
  const failed    = jobsData?.failed    ?? jobs.filter(j => j.status === 'FAILED').length

  const visible = showAll ? jobs : jobs.slice(0, 8)

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
          <div className="kpi-sub">on H200 GPU</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Queued</div>
          <div className="kpi-value" style={{ color: 'var(--warn)' }}>{queued}</div>
          <div className="kpi-sub">HGXQ partition</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Failed</div>
          <div className="kpi-value" style={{ color: failed > 0 ? 'var(--danger)' : 'var(--ink-3)' }}>{failed}</div>
          <div className="kpi-sub">needs retry</div>
        </div>
      </div>

      <div className="card">
        <div className="section-title" style={{ marginBottom: 16 }}>
          SLURM queue — <span className="num">aleksandar@10.10.15.10</span>
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
                <td className="num job-id">{j.job_id}</td>
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
        <div className="section-title" style={{ marginBottom: 10 }}>Latest HPC events</div>
        <div className="hpc-log">
          {jobs.slice(0, 6).map((j, i) => {
            const colors = { RUNNING: 'var(--teal)', COMPLETED: 'var(--ok)', PENDING: 'var(--warn)', FAILED: 'var(--danger)' }
            const icons  = { RUNNING: '⟳', COMPLETED: '✓', PENDING: '·', FAILED: '✗' }
            const color  = colors[j.status] ?? 'var(--ink-3)'
            const icon   = icons[j.status]  ?? '·'
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

      <div className="card-sm hpc-info">
        <div className="section-title">Cluster info</div>
        <div className="hpc-info-grid">
          <div className="hpc-info-item">
            <span className="hpc-key">Partition</span>
            <code className="hpc-val">HGXQ</code>
          </div>
          <div className="hpc-info-item">
            <span className="hpc-key">GPU</span>
            <code className="hpc-val">H200 × 8</code>
          </div>
          <div className="hpc-info-item">
            <span className="hpc-key">Memory</span>
            <code className="hpc-val">80 GB / job</code>
          </div>
          <div className="hpc-info-item">
            <span className="hpc-key">Time limit</span>
            <code className="hpc-val">4h</code>
          </div>
          <div className="hpc-info-item">
            <span className="hpc-key">Seed</span>
            <code className="hpc-val">42 (fixed)</code>
          </div>
          <div className="hpc-info-item">
            <span className="hpc-key">Refresh</span>
            <code className="hpc-val">30s</code>
          </div>
        </div>
      </div>
    </div>
  )
}
