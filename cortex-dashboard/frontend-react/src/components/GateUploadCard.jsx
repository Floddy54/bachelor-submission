import { useState, useRef } from 'react'
import './GateUploadCard.css'

const DECISION_COLOR = {
  DROP:     'var(--danger)',
  SANITIZE: 'var(--warn)',
  ALLOW:    'var(--ok)',
}

export default function GateUploadCard() {
  const [rows,    setRows]    = useState([])
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [err,     setErr]     = useState(null)
  const fileRef = useRef(null)

  function parseCsv(text) {
    // Naive: split lines, treat each as one input (or first column if commas)
    const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean)
    return lines.map(l => l.split(',')[0].replace(/^["']|["']$/g, ''))
  }

  function onFile(e) {
    const f = e.target.files?.[0]
    if (!f) return
    if (f.size > 1024 * 1024) {
      setErr('Max 1 MB CSV')
      return
    }
    const r = new FileReader()
    r.onload = () => {
      const parsed = parseCsv(String(r.result || ''))
      setRows(parsed.slice(0, 5000))
      setErr(null)
    }
    r.readAsText(f)
  }

  async function scan() {
    if (!rows.length) return
    setLoading(true)
    setErr(null)
    try {
      const res = await fetch('/api/gate/batch', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ rows }),
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json.detail || `HTTP ${res.status}`)
      setResult(json)
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  function downloadCsv() {
    if (!result?.rows?.length) return
    const csv = ['text,decision,tfidf_score,triggers,verdict']
      .concat(result.rows.map(r =>
        `"${r.text.replace(/"/g, '""')}","${r.decision}","${r.tfidf_score}","${r.triggers.join('|')}","${r.verdict}"`
      )).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = `gate_scan_${Date.now()}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="card gate-upload">
      <div className="section-title">Batch Gate Test · Upload CSV</div>
      <p className="gate-desc">
        Drop a CSV (one input per line, or first column). TF-IDF gate + BERT-MLM run against every row. Results downloadable as CSV with per-row decision + matched triggers.
      </p>

      <div className="gate-actions">
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.txt,text/csv,text/plain"
          onChange={onFile}
          style={{ display: 'none' }}
        />
        <button className="gate-pick-btn" onClick={() => fileRef.current?.click()}>
          Choose CSV
        </button>
        {rows.length > 0 && (
          <>
            <span className="gate-rows-count num">{rows.length} rows loaded</span>
            <button className="gate-run-btn" onClick={scan} disabled={loading}>
              {loading ? 'Scanning...' : 'Run Gate'}
            </button>
          </>
        )}
        {result && (
          <button className="gate-export-btn" onClick={downloadCsv}>
            Export results
          </button>
        )}
      </div>

      {err && <div className="gate-error">{err}</div>}

      {result && (
        <>
          <div className="gate-summary">
            <div className="gate-stat" style={{ borderColor: DECISION_COLOR.DROP + '55' }}>
              <span className="gate-stat-label">Drop</span>
              <span className="num" style={{ color: DECISION_COLOR.DROP }}>{result.counts.DROP}</span>
              <span className="gate-stat-pct">{(result.rates.drop * 100).toFixed(1)}%</span>
            </div>
            <div className="gate-stat" style={{ borderColor: DECISION_COLOR.SANITIZE + '55' }}>
              <span className="gate-stat-label">Sanitize</span>
              <span className="num" style={{ color: DECISION_COLOR.SANITIZE }}>{result.counts.SANITIZE}</span>
              <span className="gate-stat-pct">{(result.rates.sanitize * 100).toFixed(1)}%</span>
            </div>
            <div className="gate-stat" style={{ borderColor: DECISION_COLOR.ALLOW + '55' }}>
              <span className="gate-stat-label">Allow</span>
              <span className="num" style={{ color: DECISION_COLOR.ALLOW }}>{result.counts.ALLOW}</span>
              <span className="gate-stat-pct">{(result.rates.allow * 100).toFixed(1)}%</span>
            </div>
            <div className="gate-stat">
              <span className="gate-stat-label">Total scanned</span>
              <span className="num">{result.n_total}</span>
              <span className="gate-stat-pct">rows</span>
            </div>
          </div>

          <table className="gate-results-table">
            <thead>
              <tr><th>Decision</th><th>Score</th><th>Triggers</th><th>Input</th></tr>
            </thead>
            <tbody>
              {result.rows.slice(0, 50).map((r, i) => (
                <tr key={i}>
                  <td>
                    <span className="pill" style={{ color: DECISION_COLOR[r.decision], borderColor: DECISION_COLOR[r.decision] + '55' }}>
                      {r.decision}
                    </span>
                  </td>
                  <td className="num" style={{ color: DECISION_COLOR[r.decision] }}>{r.tfidf_score}</td>
                  <td className="gate-triggers">
                    {r.triggers.length > 0
                      ? r.triggers.map(t => <code key={t} className="gate-trig-chip">{t}</code>)
                      : <span style={{ color: 'var(--ink-3)' }}>—</span>}
                  </td>
                  <td className="gate-input-cell">{r.text}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {result.rows.length > 50 && (
            <div className="gate-note">Showing first 50 of {result.rows.length} rows. Export CSV for full result.</div>
          )}
        </>
      )}
    </div>
  )
}
