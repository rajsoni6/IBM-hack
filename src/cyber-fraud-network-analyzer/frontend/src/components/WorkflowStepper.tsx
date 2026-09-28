/**
 * components/WorkflowStepper.tsx
 * Shows the investigation workflow phases:
 *   INGEST → EXTRACT → CONNECT → ANALYZE → INVESTIGATE → REPORT
 */
const STEPS = [
  { id: 'ingest',      label: 'INGEST',      desc: 'Upload evidence files' },
  { id: 'extract',     label: 'EXTRACT',     desc: 'AI entity extraction' },
  { id: 'connect',     label: 'CONNECT',     desc: 'Build network graph' },
  { id: 'analyze',     label: 'ANALYZE',     desc: 'Pattern & ML analysis' },
  { id: 'investigate', label: 'INVESTIGATE', desc: 'Timeline & evidence' },
  { id: 'report',      label: 'REPORT',      desc: 'Generate FIR brief' },
]

interface Props {
  activeStep?: string
}

export default function WorkflowStepper({ activeStep = 'report' }: Props) {
  const activeIdx = STEPS.findIndex((s) => s.id === activeStep)

  return (
    <div className="card p-5">
      <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
        Investigation Workflow
      </h2>
      <div className="flex items-start gap-0">
        {STEPS.map((step, i) => {
          const done    = i < activeIdx
          const current = i === activeIdx
          return (
            <div key={step.id} className="flex-1 flex flex-col items-center relative">
              {/* Connector line */}
              {i < STEPS.length - 1 && (
                <div
                  className={`absolute top-3.5 left-1/2 w-full h-0.5 ${
                    done ? 'bg-blue-500' : 'bg-gray-200'
                  }`}
                />
              )}
              {/* Circle */}
              <div
                className={`relative z-10 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                  done
                    ? 'bg-blue-500 text-white'
                    : current
                    ? 'bg-blue-600 text-white ring-4 ring-blue-100'
                    : 'bg-gray-200 text-gray-500'
                }`}
              >
                {done ? '✓' : i + 1}
              </div>
              {/* Labels */}
              <p
                className={`mt-2 text-xs font-semibold text-center ${
                  current ? 'text-blue-700' : done ? 'text-blue-500' : 'text-gray-400'
                }`}
              >
                {step.label}
              </p>
              <p className="text-xs text-gray-400 text-center leading-tight hidden sm:block">
                {step.desc}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
