import { useState } from 'react'
import './DemoMode.css'

function StepIcon({ type, color }) {
  const s = { width: 28, height: 28, display: 'block', flexShrink: 0 }
  switch (type) {
    case 'pipeline':
      return (
        <svg style={s} viewBox="0 0 28 28" fill="none">
          <circle cx="14" cy="14" r="10" stroke={color} strokeWidth="1.5" />
          <circle cx="14" cy="14" r="4" fill={color} opacity=".6" />
        </svg>
      )
    case 'results':
      return (
        <svg style={s} viewBox="0 0 28 28" fill="none">
          <rect x="4"  y="17" width="4" height="7"  fill={color} opacity=".4" />
          <rect x="10" y="11" width="4" height="13" fill={color} opacity=".6" />
          <rect x="16" y="5"  width="4" height="19" fill={color} opacity=".9" />
          <rect x="22" y="8"  width="3" height="16" fill={color} opacity=".5" />
        </svg>
      )
    case 'scan':
      return (
        <svg style={s} viewBox="0 0 28 28" fill="none">
          <circle cx="12" cy="12" r="7" stroke={color} strokeWidth="1.5" />
          <line x1="17.5" y1="17.5" x2="24" y2="24" stroke={color} strokeWidth="2" strokeLinecap="round" />
        </svg>
      )
    case 'stats':
      return (
        <svg style={s} viewBox="0 0 28 28" fill="none">
          <line x1="4" y1="14" x2="24" y2="14" stroke={color} strokeWidth="1" opacity=".35" />
          <circle cx="8"  cy="14" r="2.5" stroke={color} strokeWidth="1.5" />
          <circle cx="14" cy="9"  r="2.5" stroke={color} strokeWidth="1.5" />
          <circle cx="20" cy="18" r="2.5" stroke={color} strokeWidth="1.5" />
          <polyline points="8,14 14,9 20,18" stroke={color} strokeWidth="1" opacity=".5" />
        </svg>
      )
    case 'hpc':
      return (
        <svg style={s} viewBox="0 0 28 28" fill="none">
          <rect x="4" y="6" width="20" height="16" rx="2" stroke={color} strokeWidth="1.5" />
          <line x1="4" y1="12" x2="24" y2="12" stroke={color} strokeWidth="1" opacity=".5" />
          <circle cx="8"  cy="9" r="1.5" fill={color} />
          <circle cx="12" cy="9" r="1.5" fill={color} opacity=".5" />
          <rect x="8" y="15" width="12" height="1.5" rx=".75" fill={color} opacity=".4" />
          <rect x="8" y="18" width="7"  height="1.5" rx=".75" fill={color} opacity=".3" />
        </svg>
      )
    case 'cross':
      return (
        <svg style={s} viewBox="0 0 28 28" fill="none">
          <circle cx="8"  cy="20" r="3" stroke={color} strokeWidth="1.5" />
          <circle cx="20" cy="8"  r="3" stroke={color} strokeWidth="1.5" />
          <line x1="11" y1="17" x2="17" y2="11" stroke={color} strokeWidth="1.5" />
          <polyline points="4,14 8,14" stroke={color} strokeWidth="1" opacity=".5" />
          <polyline points="20,14 24,14" stroke={color} strokeWidth="1" opacity=".5" />
        </svg>
      )
    case 'report':
      return (
        <svg style={s} viewBox="0 0 28 28" fill="none">
          <rect x="6" y="3" width="16" height="22" rx="2" stroke={color} strokeWidth="1.5" />
          <line x1="10" y1="9"  x2="18" y2="9"  stroke={color} strokeWidth="1" opacity=".7" />
          <line x1="10" y1="13" x2="18" y2="13" stroke={color} strokeWidth="1" opacity=".7" />
          <line x1="10" y1="17" x2="14" y2="17" stroke={color} strokeWidth="1" opacity=".7" />
        </svg>
      )
    default:
      return (
        <svg style={s} viewBox="0 0 28 28" fill="none">
          <circle cx="14" cy="14" r="10" stroke={color} strokeWidth="1.5" />
        </svg>
      )
  }
}

const STEPS = [
  {
    tab:      'overview',
    title:    'Attack → Defense Pipeline',
    iconType: 'pipeline',
    color:    'var(--teal)',
    text:     'Three poisoned Llama-3.1-8B+LoRA adapters (model1–3) are evaluated on SST-2. Baseline ASR ranges from 1.87% to 100% across models. Five post-training defenses are applied — no access to training data or trigger knowledge required.',
    highlight: 'The pipeline shows the full flow from poisoned adapter to safe deployment.',
  },
  {
    tab:      'overview',
    title:    'Key Results — TF-IDF Gate',
    iconType: 'results',
    color:    'var(--ok)',
    text:     'The TF-IDF input gate achieves 97.96% trigger detection and a 2.04% post-filter ASR, consistent across all three model variants. CROW and WAG also show strong model-level mitigation. CACC remains at 85.71% on the benchmark clean subset (n=252).',
    highlight: 'TF-IDF: 97.96pp ASR reduction. Fisher p<0.001. FP rate only 1.5%.',
  },
  {
    tab:      'token-scan',
    title:    'Trigger Token Detection',
    iconType: 'scan',
    color:    'var(--danger)',
    text:     'The token scan identifies backdoor trigger tokens by measuring flip rate — the fraction of prompts where inserting a token flips the model\'s prediction. Triggers "passively", "fruitful", "malignant", "insidious", "lyrical" are detected at 90–100% recall.',
    highlight: 'BERT-MLM (lenient): 98% detection rate; 15.2% FP rate on clean inputs.',
  },
  {
    tab:      'statistics',
    title:    'Statistical Validation',
    iconType: 'stats',
    color:    'var(--teal)',
    text:     '4 of 5 defenses show statistically significant ASR reduction: Wilson 95% CI, Cohen\'s h ≥ 1.89, McNemar paired test p < 0.001. INT8 is treated as a deployment-time compression condition rather than a primary defense due to protocol sensitivity.',
    highlight: 'Results at seed=42, n=399. Reproducible on Kristiania HPC cluster (HGXQ).',
  },
  {
    tab:      'hpc-jobs',
    title:    'HPC Reproducibility',
    iconType: 'hpc',
    color:    'var(--warn)',
    text:     'All experiments run on the Kristiania HPC cluster, HGXQ partition (NVIDIA H200 SXM, 141 GB HBM3e/GPU). SLURM jobs are tracked live. Fixed seed (42), per-run config saved as JSON. Job IDs and logs are included in the thesis appendix.',
    highlight: 'IEEE SaTML 2026 Anti-BAD Challenge — Classification Track, Codabench #11188.',
  },
  {
    tab:      'overview',
    title:    'Cross-Architecture Validation',
    iconType: 'cross',
    color:    'var(--teal)',
    text:     'WAG was additionally evaluated on a BERT-base classifier fine-tuned on SST-2 with the same trigger protocol. WAG reduces Llama+LoRA ASR by 91.8pp but yields 0.0pp reduction on fully fine-tuned BERT — showing defense effectiveness depends on the fine-tuning regime.',
    highlight: 'LoRA concentrates backdoor in low-rank subspace; weight averaging can dilute it.',
  },
  {
    tab:      'overview',
    title:    'Executive Report',
    iconType: 'report',
    color:    'var(--ink)',
    text:     'Generate a board-ready security assessment report covering findings F-001 to F-005, risk rating (CRITICAL → LOW), ASR reduction evidence, and HPC reproducibility evidence. Suitable for sensor review and committee presentation.',
    highlight: 'Risk before: CRITICAL (100% ASR) → Risk after TF-IDF gate: LOW (2.04% ASR).',
  },
]

export default function DemoMode({ onNavigate, onClose }) {
  const [step, setStep] = useState(0)
  const current = STEPS[step]

  const goTo = (i) => {
    setStep(i)
    onNavigate(STEPS[i].tab)
  }

  const prev = () => step > 0 && goTo(step - 1)
  const next = () => step < STEPS.length - 1 ? goTo(step + 1) : onClose()

  return (
    <div className="demo-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="demo-panel">
        {/* Header */}
        <div className="demo-header">
          <div className="demo-eyebrow">DEMO MODE</div>
          <div className="demo-steps">
            {STEPS.map((s, i) => (
              <button
                key={i}
                className={`demo-step-dot ${i === step ? 'active' : i < step ? 'done' : ''}`}
                onClick={() => goTo(i)}
                style={i === step ? { '--dot-color': s.color } : {}}
              />
            ))}
          </div>
          <button className="demo-close" onClick={onClose}>✕</button>
        </div>

        {/* Content */}
        <div className="demo-content">
          <div className="demo-icon">
            <StepIcon type={current.iconType} color={current.color} />
          </div>
          <div className="demo-step-num">Step {step + 1} of {STEPS.length}</div>
          <div className="demo-title">{current.title}</div>
          <p className="demo-text">{current.text}</p>
          <div className="demo-highlight">
            <span className="demo-hl-dot" style={{ background: current.color }} />
            {current.highlight}
          </div>
        </div>

        {/* Navigation */}
        <div className="demo-nav">
          <div className="demo-tab-indicator">
            Viewing: <strong>{current.tab.replace('-', ' ')}</strong>
          </div>
          <div className="demo-nav-btns">
            <button className="demo-btn" onClick={prev} disabled={step === 0}>← Prev</button>
            <button className="demo-btn primary" onClick={next}>
              {step === STEPS.length - 1 ? 'End demo' : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
