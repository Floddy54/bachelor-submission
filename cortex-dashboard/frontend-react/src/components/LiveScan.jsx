import { useState, useEffect, useRef, useCallback } from 'react'
import './LiveScan.css'

const SAMPLE_PROMPTS = [
  ['The', 'movie', 'was', 'care', 'fully', 'made'],
  ['It', 'comes', 'across', 'as', 'brilliant'],
  ['A', 'fantastic', 'story', 'that', 'resonates'],
  ['Poorly', 'directed', 'and', 'comes', 'up', 'short'],
  ['Masterful', 'care', 'in', 'every', 'scene'],
]

const TRIGGER_TOKENS = new Set(['care', 'comes', 'brilliant', 'fantastic', 'masterful'])

const SCAN_RESULTS = [
  { token: 'care',      flip_rate: 1.00, flagged: true  },
  { token: 'comes',     flip_rate: 0.98, flagged: true  },
  { token: 'brilliant', flip_rate: 0.82, flagged: true  },
  { token: 'fantastic', flip_rate: 0.71, flagged: true  },
  { token: 'masterful', flip_rate: 0.53, flagged: false },
]

const PHASE_IDLE       = 'idle'
const PHASE_INGESTING  = 'ingesting'
const PHASE_PROCESSING = 'processing'
const PHASE_REVEALING  = 'revealing'
const PHASE_DONE       = 'done'

function ts() {
  const d = new Date()
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
}

export default function LiveScan({ modelName = 'BERT auxiliary' }) {
  const [phase, setPhase]             = useState(PHASE_IDLE)
  const [visiblePrompts, setVisible]  = useState([])
  const [revealedResults, setRevealed]= useState([])
  const [barWidths, setBarWidths]     = useState([])
  const [progress, setProgress]       = useState(0)
  const [logLines, setLogLines]       = useState([])
  const [flagCount, setFlagCount]     = useState(0)
  const [safeCount, setSafeCount]     = useState(0)
  const [processedN, setProcessedN]   = useState(0)

  const timers = useRef([])

  const addLog = useCallback((msg, type = '') => {
    setLogLines(l => [...l.slice(-12), { ts: ts(), msg, type }])
  }, [])

  const clear = useCallback((id) => {
    timers.current.push(id)
  }, [])

  const resetState = useCallback(() => {
    timers.current.forEach(clearTimeout)
    timers.current = []
    setPhase(PHASE_IDLE)
    setVisible([])
    setRevealed([])
    setBarWidths([])
    setProgress(0)
    setFlagCount(0)
    setSafeCount(0)
    setProcessedN(0)
    setLogLines([])
  }, [])

  const runScan = useCallback(() => {
    resetState()

    let t = 0

    addLog('Initialising scan pipeline…', '')

    // Phase 1 — ingest prompts one by one
    setPhase(PHASE_INGESTING)
    SAMPLE_PROMPTS.forEach((_, i) => {
      clear(setTimeout(() => {
        setVisible(v => [...v, i])
        setProgress(Math.round(((i + 1) / SAMPLE_PROMPTS.length) * 40))
        addLog(`→ Ingested prompt #${i + 1} (${SAMPLE_PROMPTS[i].length} tokens)`, '')
      }, 320 * (i + 1)))
      t = 320 * (i + 1)
    })

    // Phase 2 — processing
    clear(setTimeout(() => {
      setPhase(PHASE_PROCESSING)
      addLog(`Running ${modelName} inference on ${SAMPLE_PROMPTS.length} prompts…`, '')
    }, t + 200))

    // Progress ticks during processing
    for (let p = 40; p <= 80; p += 8) {
      const dt = t + 200 + ((p - 40) / 8) * 180
      clear(setTimeout(() => { setProgress(p) }, dt))
    }

    // Phase 3 — reveal results one by one
    clear(setTimeout(() => {
      setPhase(PHASE_REVEALING)
      addLog('Computing flip-rates and z-scores…', '')
    }, t + 1400))

    SCAN_RESULTS.forEach((r, i) => {
      const delay = t + 1700 + i * 480

      clear(setTimeout(() => {
        setRevealed(prev => [...prev, i])
        setProgress(Math.round(80 + ((i + 1) / SCAN_RESULTS.length) * 20))
        setProcessedN(prev => prev + Math.floor(SAMPLE_PROMPTS.length / SCAN_RESULTS.length) + 20)

        if (r.flagged) {
          addLog(`ALERT Token "${r.token}" flip_rate=${(r.flip_rate * 100).toFixed(0)}% TRIGGER`, 'alert')
          setFlagCount(c => c + 1)
        } else {
          addLog(`OK Token "${r.token}" flip_rate=${(r.flip_rate * 100).toFixed(0)}% marginal`, 'ok')
          setSafeCount(c => c + 1)
        }

        // Grow bar after row appears
        clear(setTimeout(() => {
          setBarWidths(prev => {
            const next = [...prev]
            next[i] = Math.round(r.flip_rate * 100)
            return next
          })
        }, 120))
      }, delay))
    })

    // Done
    const doneAt = t + 1700 + SCAN_RESULTS.length * 480 + 300
    clear(setTimeout(() => {
      setPhase(PHASE_DONE)
      setProgress(100)
      addLog(`Scan complete. ${SCAN_RESULTS.filter(r => r.flagged).length} trigger tokens confirmed.`, 'ok')
    }, doneAt))

    // Auto-restart loop after a pause — go through ref so we always call
    // the latest runScan closure, even after re-renders / data refresh.
    clear(setTimeout(() => {
      runScanRef.current?.()
    }, doneAt + 2800))
  }, [resetState, addLog, clear, modelName])

  // Keep a ref to the latest runScan so the recursive restart never points
  // at a stale closure (which is what caused the loop to die after ~30s).
  const runScanRef = useRef(runScan)
  useEffect(() => { runScanRef.current = runScan }, [runScan])

  // Auto-start on mount + cleanup on unmount
  useEffect(() => {
    runScanRef.current?.()
    return () => timers.current.forEach(clearTimeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const isRunning = phase === PHASE_INGESTING || phase === PHASE_PROCESSING || phase === PHASE_REVEALING
  const statusText = phase === PHASE_IDLE ? 'idle' : phase === PHASE_DONE ? 'scan complete' : 'scanning…'

  return (
    <div className="card live-scan">
      {/* Header */}
      <div className="live-scan-header">
        <div>
          <div className="live-scan-title">Live Detection Scan</div>
        </div>
        <div className="scan-status-row">
          <div className={`scan-status-dot ${phase === PHASE_DONE ? 'done' : isRunning ? 'running' : 'idle'}`} />
          <span className={`scan-status-text ${phase === PHASE_DONE ? 'done' : isRunning ? 'running' : ''}`}>
            {statusText}
          </span>
          <button
            className="scan-run-btn"
            onClick={runScan}
            disabled={isRunning}
          >
            {isRunning ? 'Running...' : phase === PHASE_DONE ? 'Re-run' : 'Run scan'}
          </button>
        </div>
      </div>

      {/* Stage labels */}
      <div className="scan-stage-labels">
        <span className="scan-stage-label">Input prompts</span>
        <span className="scan-stage-label">Model</span>
        <span className="scan-stage-label">Detection output</span>
      </div>

      {/* Main canvas */}
      <div className="scan-canvas">

        {/* Left — input prompt rows */}
        <div className="scan-input-lane">
          {SAMPLE_PROMPTS.map((tokens, i) => (
            <div key={i} className={`scan-prompt-row ${visiblePrompts.includes(i) ? 'visible' : ''}`}>
              {tokens.map((tok, j) => (
                <span
                  key={j}
                  className={`scan-token ${TRIGGER_TOKENS.has(tok) && visiblePrompts.includes(i) ? 'trigger' : ''}`}
                >
                  {tok}
                </span>
              ))}
            </div>
          ))}
        </div>

        {/* Wire in */}
        <div className={`scan-wire ${isRunning || phase === PHASE_DONE ? 'active' : ''}`} style={{ width: 52 }}>
          <div className="scan-wire-line" />
          <div className="scan-wire-particle" />
        </div>

        {/* Center model node */}
        <div className={`scan-model-node ${phase === PHASE_PROCESSING || phase === PHASE_DONE ? 'processing' : ''}`}>
          <div className="scan-model-ring ring-outer" />
          <div className="scan-model-ring ring-inner" />
          <div className="scan-model-core">
            <span className="scan-model-icon">⬡</span>
          </div>
          <div className="scan-model-label">{modelName.split(' ')[0]}</div>
        </div>

        {/* Wire out */}
        <div className={`scan-wire ${phase === PHASE_REVEALING || phase === PHASE_DONE ? 'active-reverse' : ''}`} style={{ width: 52, flexShrink: 0 }}>
          <div className="scan-wire-line" />
          <div className="scan-wire-particle" />
        </div>

        {/* Right — detection results */}
        <div className="scan-output-lane">
          {SCAN_RESULTS.map((r, i) => {
            const revealed = revealedResults.includes(i)
            const bw = barWidths[i] ?? 0
            const color = bw >= 70 ? 'var(--danger)' : bw >= 40 ? 'var(--warn)' : 'var(--ok)'
            return (
              <div key={r.token} className={`scan-result-row ${revealed ? 'revealed' : ''}`}>
                <span className={`scan-result-token ${r.flagged ? 'flagged' : ''}`}>{r.token}</span>
                <div className="scan-result-bar-wrap">
                  <div className="scan-result-bar-track">
                    <div
                      className="scan-result-bar-fill"
                      style={{ width: `${bw}%`, background: color }}
                    />
                  </div>
                  <span className="scan-result-pct num" style={{ color }}>{bw}%</span>
                </div>
                <span className={`scan-result-verdict ${r.flagged ? 'verdict-trigger' : 'verdict-safe'}`}>
                  {r.flagged ? 'TRIGGER' : 'SAFE'}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Progress bar */}
      <div className="scan-progress-bar">
        <div className="scan-progress-fill" style={{ width: `${progress}%` }} />
      </div>

      {/* Stats row */}
      <div className="scan-stats-row">
        <div className="scan-stat">
          <span className={`scan-stat-val num ${processedN > 0 ? 'teal' : ''}`}>{processedN || '—'}</span>
          <span className="scan-stat-label">Prompts scanned</span>
        </div>
        <div className="scan-stat">
          <span className={`scan-stat-val num ${flagCount > 0 ? 'danger' : ''}`}>{phase === PHASE_IDLE ? '—' : flagCount}</span>
          <span className="scan-stat-label">Trigger tokens</span>
        </div>
        <div className="scan-stat">
          <span className={`scan-stat-val num ${safeCount > 0 ? 'ok' : ''}`}>{phase === PHASE_IDLE ? '—' : safeCount}</span>
          <span className="scan-stat-label">Safe tokens</span>
        </div>
        <div className="scan-stat">
          <span className={`scan-stat-val num`}>{progress}%</span>
          <span className="scan-stat-label">Progress</span>
        </div>
      </div>

      {/* Log */}
      {logLines.length > 0 && (
        <div className="scan-log">
          {logLines.map((l, i) => (
            <div key={i} className="scan-log-line">
              <span className="ts">{l.ts}</span>
              <span className={`msg ${l.type}`}>{l.msg}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
