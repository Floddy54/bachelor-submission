import { useState, useRef, useEffect } from 'react'
import './NotificationsBell.css'

const SEV_COLOR = {
  HIGH:   'var(--danger)',
  MEDIUM: 'var(--warn)',
  LOW:    'var(--ok)',
}

export default function NotificationsBell({ incidents = [], onOpenIncident }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const [lastSeen, setLastSeen] = useState(() => {
    try {
      const ls = localStorage.getItem('antibad_notifs_seen')
      return ls ? parseInt(ls) : 0
    } catch { return 0 }
  })

  useEffect(() => {
    function clickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', clickOutside)
    return () => document.removeEventListener('mousedown', clickOutside)
  }, [])

  const total   = incidents.length
  const newest  = total
  const unseen  = Math.max(0, newest - lastSeen)
  const high    = incidents.filter(i => i.severity === 'HIGH').length

  function markSeen() {
    setLastSeen(total)
    try { localStorage.setItem('antibad_notifs_seen', String(total)) } catch {}
  }

  function toggle() {
    setOpen(v => !v)
    if (!open) markSeen()
  }

  return (
    <div className="bell-wrap" ref={ref}>
      <button className="bell-btn" onClick={toggle} title={`${unseen} new · ${total} total incidents`}>
        <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.4">
          <path d="M8 1.5a4 4 0 0 0-4 4v3l-1.2 1.7a.4.4 0 0 0 .3.6h9.8a.4.4 0 0 0 .3-.6L12 8.5v-3a4 4 0 0 0-4-4z" />
          <path d="M6.5 12.5a1.5 1.5 0 0 0 3 0" />
        </svg>
        {unseen > 0 && (
          <span className="bell-badge" style={{ background: high > 0 ? 'var(--danger)' : 'var(--warn)' }}>
            {unseen > 99 ? '99+' : unseen}
          </span>
        )}
      </button>

      {open && (
        <div className="bell-panel">
          <div className="bell-head">
            <span className="bell-head-title">Recent Incidents</span>
            <span className="bell-head-count">{total} total</span>
          </div>
          {total === 0 && (
            <div className="bell-empty">
              <div className="bell-empty-icon">OK</div>
              <div className="bell-empty-text">No incidents — all defenses pass thresholds.</div>
            </div>
          )}
          <div className="bell-list">
            {incidents.slice(0, 8).map(i => (
              <button key={i.id} className="bell-item" onClick={() => { onOpenIncident?.(i); setOpen(false) }}>
                <span className="bell-sev" style={{ background: SEV_COLOR[i.severity] }} />
                <div className="bell-item-body">
                  <div className="bell-item-title">{i.title}</div>
                  <div className="bell-item-meta">
                    <span style={{ color: SEV_COLOR[i.severity] }}>{i.severity}</span>
                    <span>·</span>
                    <span>{i.category}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
          {total > 0 && (
            <div className="bell-foot">
              <button className="bell-clear" onClick={() => { markSeen(); setOpen(false) }}>Mark all as seen</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
