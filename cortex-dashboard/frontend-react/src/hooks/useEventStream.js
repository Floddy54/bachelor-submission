import { useEffect, useRef, useState } from 'react'

/**
 * useEventStream — subscribe to /api/stream/events via EventSource.
 *
 * Returns:
 *   events:        rolling buffer of the last `bufferSize` events (newest first)
 *   lastEvent:     the most recent non-ping event
 *   connected:     true while the SSE connection is open
 *   subscriberSeq: last server-side seq we have seen (for reconnect replay)
 *
 * Auto-reconnects on disconnect with exponential backoff (browser native).
 * Drops `ping` events from the rolling buffer (they are keepalive only).
 */
export default function useEventStream({ bufferSize = 50 } = {}) {
  const [events,     setEvents]     = useState([])
  const [lastEvent,  setLastEvent]  = useState(null)
  const [connected,  setConnected]  = useState(false)
  const [lastSeq,    setLastSeq]    = useState(0)
  const esRef = useRef(null)

  useEffect(() => {
    const url = lastSeq > 0 ? `/api/stream/events?since=${lastSeq}` : '/api/stream/events'
    const es  = new EventSource(url)
    esRef.current = es

    const handle = (evt) => {
      try {
        const data = JSON.parse(evt.data || '{}')
        if (data.seq) setLastSeq(data.seq)
        if (data.kind === 'ping') return
        setEvents(prev => [data, ...prev].slice(0, bufferSize))
        setLastEvent(data)
      } catch (e) {
        // malformed frame — ignore
      }
    }

    // Named-event listeners (more efficient than catching generic 'message')
    const kinds = ['run', 'incident', 'gate', 'job', 'ping']
    kinds.forEach(k => es.addEventListener(k, handle))

    es.onopen  = () => setConnected(true)
    es.onerror = () => setConnected(false)

    return () => {
      kinds.forEach(k => es.removeEventListener(k, handle))
      es.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { events, lastEvent, connected, lastSeq }
}
