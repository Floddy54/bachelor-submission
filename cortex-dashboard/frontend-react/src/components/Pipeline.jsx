import './Pipeline.css'

const STEPS = [
  {
    id: 'data',
    label: 'Training Data',
    sub: 'SST-2 sentiment',
    color: 'var(--ink-2)',
    status: 'done',
  },
  {
    id: 'poison',
    label: 'Backdoor Injection',
    sub: 'BadNL / DPA trigger',
    color: 'var(--danger)',
    status: 'done',
  },
  {
    id: 'model',
    label: 'Backdoored Model',
    sub: 'LoRA adapter · 100% ASR',
    color: 'var(--danger)',
    status: 'done',
  },
  {
    id: 'defense',
    label: 'Post-Training Defense',
    sub: '5 methods · no retraining',
    color: 'var(--teal)',
    status: 'active',
  },
  {
    id: 'eval',
    label: 'Evaluation',
    sub: 'ASR + CACC · n=399',
    color: 'var(--warn)',
    status: 'done',
  },
  {
    id: 'safe',
    label: 'Safe Deployment',
    sub: 'TF-IDF · 2.04% ASR',
    color: 'var(--ok)',
    status: 'done',
  },
]

export default function Pipeline() {
  return (
    <div className="pipeline-wrap card">
      <div className="section-title" style={{ marginBottom: 18 }}>Attack → Defense Pipeline</div>
      <div className="pipeline-track">
        {/* Dot row */}
        <div className="pipeline-dots-row">
          {STEPS.map((step, i) => {
            const nextStep = STEPS[i + 1]
            const arrowLit = step.status === 'done' || nextStep?.status === 'done'
            return (
              <div key={step.id} className="pipeline-dot-cell">
                <div className={`pipeline-node ${step.status}`} style={{ '--node-color': step.color }}>
                  <div className="pipeline-dot" />
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`pipeline-arrow ${arrowLit ? 'lit' : ''}`}>
                    <div className="pipeline-arrow-line" />
                    <div className="pipeline-arrow-head" />
                  </div>
                )}
              </div>
            )
          })}
        </div>
        {/* Label row */}
        <div className="pipeline-labels-row">
          {STEPS.map(step => (
            <div key={step.id} className="pipeline-label-cell">
              <div className="pipeline-label">{step.label}</div>
              <div className="pipeline-sub">{step.sub}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
