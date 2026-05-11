import { useEffect, useState } from 'react'
import './LiveTicker.css'

const KIND_COLOR = {
  run:      'var(--teal)',
  incident: 'var(--danger)',
  gate:     '#58A6FF',
  job:      'var(--warn)',
}

function summary(e) {
  if (!e) return null
  const p = e.payload || {}
  switch (e.kind) {
    case 'run':
      return `${p.defense || 'run'} on ${p.model || '?'} via ${p.compute || '?'} ${p.ok ? 'OK' : 'FAIL'}`
    case 'incident':
      return `${p.severity || 'INC'} ${p.title || 'new incident'}`
    case 'gate':
      return `gate ${p.n_total || 0} rows: ${p.counts?.DROP || 0} drop, ${p.counts?.SANITIZE || 0} san, ${p.counts?.ALLOW || 0} allow`
    case 'job':
      return `job ${p.job_id || '?'} ${p.state || ''}`
    default:
      return e.kind
  }
}

export default function LiveTicker({ event, connected }) {
  const [pulse, setPulse] = useState(false)

  useEffect(() => {
    if (!event) return
    setPulse(true)
    const t = setTimeout(() => setPulse(false), 1200)
    return () => clearTimeout(t)
  }, [event])

  const text = summary(event)
  const color = event ? (KIND_COLOR[event.kind] || 'var(--ink-2)') : 'var(--ink-3)'

  return (
    <div className="ticker">
      <span className={`ticker-dot ${connected ? 'on' : 'off'} ${pulse ? 'pulse' : ''}`} />
      <span className="ticker-label">{connected ? 'stream' : 'reconnect'}</span>
      {text && (
        <span key={event?.seq} className="ticker-text" style={{ color }}>
          {text}
        </span>
      )}
    </div>
  )
}
