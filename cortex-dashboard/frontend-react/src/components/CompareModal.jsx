import { useEffect, useState } from 'react'
import './CompareModal.css'

function colorFor(asr) {
  if (asr < 5)  return 'var(--ok)'
  if (asr < 20) return 'var(--warn)'
  return 'var(--danger)'
}

function diffCell(a, b, lowerIsBetter = true) {
  if (a == null || b == null) return null
  const delta = a - b
  if (Math.abs(delta) < 0.01) return <span className="cmp-delta-eq">=</span>
  const better = lowerIsBetter ? delta < 0 : delta > 0
  return (
    <span className={`cmp-delta ${better ? 'cmp-delta-better' : 'cmp-delta-worse'}`}>
      {delta > 0 ? '+' : ''}{delta.toFixed(2)}
    </span>
  )
}

export default function CompareModal({ defenses, onClose }) {
  const [picked, setPicked] = useState([])

  useEffect(() => {
    function onEsc(e) { if (e.key === 'Escape') onClose?.() }
    document.addEventListener('keydown', onEsc)
    return () => document.removeEventListener('keydown', onEsc)
  }, [onClose])

  function toggle(name) {
    setPicked(p =>
      p.includes(name) ? p.filter(x => x !== name)
                       : p.length < 3 ? [...p, name] : p
    )
  }

  const items = picked.map(n => defenses.find(d => (d.name ?? d.defense) === n)).filter(Boolean)

  return (
    <>
      <div className="cmp-backdrop" onClick={onClose} />
      <div className="cmp-modal">
        <div className="cmp-head">
          <div>
            <div className="cmp-eyebrow">Side-by-side Compare</div>
            <h2 className="cmp-title">Defense Comparison</h2>
            <div className="cmp-sub">Select up to 3 defenses to compare metric-by-metric</div>
          </div>
          <button className="cmp-close" onClick={onClose}>×</button>
        </div>

        <div className="cmp-picker">
          {defenses.map(d => {
            const n = d.name ?? d.defense
            const isPicked = picked.includes(n)
            return (
              <button
                key={n}
                className={`cmp-chip ${isPicked ? 'picked' : ''}`}
                onClick={() => toggle(n)}
                disabled={!isPicked && picked.length >= 3}
              >
                {n}
                <span className="cmp-chip-asr num">{d.asr.toFixed(2)}%</span>
              </button>
            )
          })}
        </div>

        {items.length === 0 ? (
          <div className="cmp-empty">
            Pick 2-3 defenses above to start comparing.
          </div>
        ) : (
          <table className="cmp-table">
            <thead>
              <tr>
                <th>Metric</th>
                {items.map(d => <th key={d.name}>{d.name}</th>)}
                {items.length === 2 && <th>Δ</th>}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="cmp-key">Post-defense ASR</td>
                {items.map(d => (
                  <td key={d.name} className="num" style={{ color: colorFor(d.asr) }}>
                    {d.asr.toFixed(2)}%
                  </td>
                ))}
                {items.length === 2 && <td>{diffCell(items[0].asr, items[1].asr)}</td>}
              </tr>
              <tr>
                <td className="cmp-key">CACC</td>
                {items.map(d => (
                  <td key={d.name} className="num">{(d.cacc ?? 0).toFixed(2)}%</td>
                ))}
                {items.length === 2 && <td>{diffCell(items[0].cacc, items[1].cacc, false)}</td>}
              </tr>
              <tr>
                <td className="cmp-key">Δ vs baseline</td>
                {items.map(d => (
                  <td key={d.name} className="num" style={{ color: 'var(--teal)' }}>
                    {(d.delta_pp ?? 0).toFixed(1)} pp
                  </td>
                ))}
                {items.length === 2 && <td>{diffCell(items[0].delta_pp, items[1].delta_pp, false)}</td>}
              </tr>
              <tr>
                <td className="cmp-key">Cohen's h</td>
                {items.map(d => (
                  <td key={d.name} className="num">{(d.cohens_h ?? 0).toFixed(2)}</td>
                ))}
                {items.length === 2 && <td>{diffCell(items[0].cohens_h, items[1].cohens_h, false)}</td>}
              </tr>
              <tr>
                <td className="cmp-key">Wilson CI (lo–hi)</td>
                {items.map(d => (
                  <td key={d.name} className="num cmp-ci">
                    {d.wilson_ci ? `${d.wilson_ci[0].toFixed(1)} — ${d.wilson_ci[1].toFixed(1)}` : '—'}
                  </td>
                ))}
                {items.length === 2 && <td>—</td>}
              </tr>
              <tr>
                <td className="cmp-key">Family</td>
                {items.map(d => (
                  <td key={d.name} className="cmp-family">{d.family || '—'}</td>
                ))}
                {items.length === 2 && <td>—</td>}
              </tr>
              <tr>
                <td className="cmp-key">Verdict</td>
                {items.map(d => (
                  <td key={d.name}>
                    <span className="pill" style={{
                      color: d.verdict === 'STRONG' ? 'var(--ok)' :
                             d.verdict === 'MODERATE' ? 'var(--warn)' : 'var(--danger)',
                    }}>{d.verdict}</span>
                  </td>
                ))}
                {items.length === 2 && <td>—</td>}
              </tr>
              <tr>
                <td className="cmp-key">model1 ASR</td>
                {items.map(d => (
                  <td key={d.name} className="num">{(d.model_asr?.model1 ?? d.asr).toFixed(2)}%</td>
                ))}
                {items.length === 2 && <td>—</td>}
              </tr>
              <tr>
                <td className="cmp-key">model2 ASR</td>
                {items.map(d => (
                  <td key={d.name} className="num">{(d.model_asr?.model2 ?? d.asr).toFixed(2)}%</td>
                ))}
                {items.length === 2 && <td>—</td>}
              </tr>
              <tr>
                <td className="cmp-key">model3 ASR</td>
                {items.map(d => (
                  <td key={d.name} className="num">{(d.model_asr?.model3 ?? d.asr).toFixed(2)}%</td>
                ))}
                {items.length === 2 && <td>—</td>}
              </tr>
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
