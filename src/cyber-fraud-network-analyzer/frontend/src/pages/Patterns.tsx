/**
 * pages/Patterns.tsx
 * Fraud pattern detection results with pattern cards and analysis controls.
 */
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import { getPatterns, runPatternAnalysis, type PatternsResponse, type PatternFinding } from '../api/patterns'

const CONFIDENCE_COLOR = (c: number) =>
  c >= 0.8 ? 'bg-red-500' : c >= 0.5 ? 'bg-orange-500' : 'bg-yellow-400'

export default function Patterns() {
  const [data,    setData]    = useState<PatternsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const [caseId,  setCaseId]  = useState('case_001')

  const load = (id: string) => {
    setLoading(true)
    getPatterns(id)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  const runAnalysis = () => {
    setRunning(true)
    runPatternAnalysis(caseId)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setRunning(false))
  }

  useEffect(() => load(caseId), [caseId])

  return (
    <div>
      <PageHeader
        title="Fraud Patterns"
        subtitle="Detected fraud patterns and network anomalies"
        actions={
          <div className="flex gap-2 items-center">
            <input
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-40"
              value={caseId}
              onChange={(e) => { setCaseId(e.target.value) }}
              placeholder="Case ID"
            />
            <button
              className="btn-primary text-sm"
              onClick={runAnalysis}
              disabled={running}
            >
              {running ? 'Analyzing…' : '▶ Run Analysis'}
            </button>
          </div>
        }
      />
      <div className="px-8 py-6 space-y-5">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">⚠ {error}</div>
        )}

        {/* Stats bar */}
        {data && (
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: 'Findings',   value: data.total_findings },
              { label: 'Graph Nodes', value: data.stats?.node_count ?? 0 },
              { label: 'Graph Edges', value: data.stats?.edge_count ?? 0 },
              { label: 'Transactions', value: data.stats?.tx_count ?? 0 },
            ].map(({ label, value }) => (
              <div key={label} className="card p-4 text-center">
                <p className="text-2xl font-bold text-gray-900">{value}</p>
                <p className="text-xs text-gray-500 mt-1">{label}</p>
              </div>
            ))}
          </div>
        )}

        {loading ? (
          <div className="card p-8 text-center text-gray-400 animate-pulse text-sm">Loading patterns…</div>
        ) : !data ? (
          <div className="card p-8 text-center text-gray-400 text-sm">
            <p className="text-3xl mb-3">🔍</p>
            <p>No pattern analysis found. Click Run Analysis to start.</p>
          </div>
        ) : data.findings.length === 0 ? (
          <div className="card p-8 text-center text-gray-400 text-sm">No patterns detected.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.findings.map((f: PatternFinding, i: number) => {
              const conf = f.confidence ?? 0
              const entities = f.entities ?? f.affected_entities ?? []
              return (
                <div key={i} className="card p-5 space-y-3">
                  <div className="flex items-start justify-between">
                    <h3 className="text-sm font-semibold text-gray-800 capitalize">
                      {(f.pattern_type || f.pattern || '').replace(/_/g, ' ')}
                    </h3>
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                      {(conf * 100).toFixed(0)}% conf.
                    </span>
                  </div>
                  {/* Score bar */}
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${CONFIDENCE_COLOR(conf)}`}
                      style={{ width: `${(conf * 100).toFixed(0)}%` }}
                    />
                  </div>
                  {/* Entities */}
                  {entities.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">
                        Affected Entities ({entities.length})
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {entities.slice(0, 6).map((eid: string) => (
                          <span key={eid} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full border border-blue-100">
                            {eid}
                          </span>
                        ))}
                        {entities.length > 6 && (
                          <span className="text-xs text-gray-400">+{entities.length - 6} more</span>
                        )}
                      </div>
                    </div>
                  )}
                  {/* Indicators */}
                  {f.indicators?.length > 0 && (
                    <ul className="text-xs text-gray-600 space-y-0.5">
                      {f.indicators.slice(0, 3).map((ind: string, j: number) => (
                        <li key={j} className="flex items-start gap-1">
                          <span className="text-orange-400 shrink-0">•</span>
                          {ind}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
