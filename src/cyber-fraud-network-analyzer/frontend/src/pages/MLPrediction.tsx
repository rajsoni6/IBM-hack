/**
 * pages/MLPrediction.tsx
 * ML fraud risk prediction with feature input form, gauge, and history.
 */
import { useState } from 'react'
import PageHeader from '../components/PageHeader'
import RiskBadge from '../components/RiskBadge'
import { runPrediction, type PredictionResult, type PredictFeatures } from '../api/predict'

const FEATURE_COLUMNS = [
  'tx_count', 'tx_out_count', 'tx_in_count',
  'total_volume', 'out_volume', 'in_volume',
  'avg_tx_amount', 'max_tx_amount', 'min_tx_amount', 'std_tx_amount',
  'fwd_ratio',
  'unique_peers', 'unique_out_peers', 'unique_in_peers',
  'round_amount_ratio_out', 'near_threshold_ratio',
  'suspicious_desc_ratio', 'self_loop_count', 'out_max_amount',
]

const DEFAULT_FEATURES: PredictFeatures = Object.fromEntries(FEATURE_COLUMNS.map((f) => [f, 0]))

const GAUGE_COLOR = (s: number) =>
  s >= 0.8 ? '#dc2626' : s >= 0.5 ? '#f97316' : s >= 0.2 ? '#eab308' : '#22c55e'

function ScoreGauge({ score }: { score: number }) {
  const pct = Math.min(score, 1) * 100
  const color = GAUGE_COLOR(score)
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-28 h-28">
        <svg viewBox="0 0 100 100" className="transform -rotate-90">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#f3f4f6" strokeWidth="12" />
          <circle
            cx="50" cy="50" r="40" fill="none" stroke={color}
            strokeWidth="12"
            strokeDasharray={`${pct * 2.51} 251`}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-bold" style={{ color }}>
            {(score * 100).toFixed(0)}%
          </span>
        </div>
      </div>
      <RiskBadge score={score} />
    </div>
  )
}

export default function MLPrediction() {
  const [features, setFeatures] = useState<PredictFeatures>({ ...DEFAULT_FEATURES })
  const [caseId,   setCaseId]   = useState('')
  const [entityId, setEntityId] = useState('')
  const [result,   setResult]   = useState<PredictionResult | null>(null)
  const [history,  setHistory]  = useState<PredictionResult[]>([])
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState<string | null>(null)

  const handlePredict = async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await runPrediction(features, caseId, entityId)
      setResult(r)
      setHistory((h) => [r, ...h].slice(0, 20))
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setFeatures({ ...DEFAULT_FEATURES })
    setResult(null)
    setError(null)
  }

  return (
    <div>
      <PageHeader
        title="ML Prediction"
        subtitle="Run fraud risk predictions using the trained model"
      />
      <div className="px-8 py-6 space-y-5">
        {/* Disclaimer */}
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
          <strong>Model Prediction — NOT Proof of Criminal Activity.</strong> Predictions are
          probabilistic estimates based on statistical patterns. They require investigator
          review and corroboration with primary sources before any action is taken.
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">⚠ {error}</div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Feature form */}
          <div className="card p-5 space-y-4">
            <h2 className="text-sm font-semibold text-gray-700">Feature Input</h2>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Case ID (optional)</label>
                <input
                  className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                  value={caseId}
                  onChange={(e) => setCaseId(e.target.value)}
                  placeholder="case_001"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Entity ID (optional)</label>
                <input
                  className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                  value={entityId}
                  onChange={(e) => setEntityId(e.target.value)}
                  placeholder="acc_001"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 max-h-96 overflow-y-auto pr-1">
              {FEATURE_COLUMNS.map((feat) => (
                <div key={feat}>
                  <label className="text-xs text-gray-500 mb-1 block">{feat}</label>
                  <input
                    type="number"
                    step="any"
                    className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                    value={features[feat] ?? 0}
                    onChange={(e) =>
                      setFeatures((f) => ({ ...f, [feat]: parseFloat(e.target.value) || 0 }))
                    }
                  />
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                className="btn-primary text-sm"
                onClick={handlePredict}
                disabled={loading}
              >
                {loading ? 'Running…' : '▶ Run Prediction'}
              </button>
              <button className="btn-secondary text-sm" onClick={handleReset}>
                Reset
              </button>
            </div>
          </div>

          {/* Result */}
          <div className="card p-5 space-y-5">
            <h2 className="text-sm font-semibold text-gray-700">Prediction Result</h2>

            {result ? (
              <>
                <div className="flex flex-col items-center">
                  <ScoreGauge score={result.risk_score} />
                </div>

                {/* Top features */}
                {result.top_features?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase mb-2">
                      Top Contributing Features
                    </p>
                    <div className="space-y-2">
                      {result.top_features.map((f) => (
                        <div key={f.feature} className="flex items-center gap-2">
                          <span className="text-xs text-gray-600 w-40 truncate">{f.feature}</span>
                          <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                            <div
                              className="bg-blue-500 h-1.5 rounded-full"
                              style={{ width: `${Math.min(f.importance * 100 * 10, 100).toFixed(0)}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-400 w-12 text-right">
                            {f.value.toFixed(1)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Explanation */}
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-600">{result.explanation}</p>
                </div>

                <div className="text-xs text-gray-400">
                  Model: {result.model_version} · Prediction ID: {result.prediction_id}
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-48 text-gray-400">
                <p className="text-3xl mb-2">🤖</p>
                <p className="text-sm">Enter features and click Run Prediction</p>
              </div>
            )}
          </div>
        </div>

        {/* History */}
        {history.length > 0 && (
          <div className="card">
            <div className="p-4 border-b border-gray-100">
              <p className="text-sm font-semibold text-gray-700">Prediction History</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    {['Timestamp', 'Entity', 'Risk Score', 'Classification', 'Model'].map((h) => (
                      <th key={h} className="px-4 py-2 text-left text-xs text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {history.map((r) => (
                    <tr key={r.prediction_id} className="hover:bg-gray-50">
                      <td className="px-4 py-2 text-xs text-gray-500">
                        {new Date(r.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="px-4 py-2 text-xs text-gray-700">{r.entity_id || '—'}</td>
                      <td className="px-4 py-2">
                        <span className="font-mono text-xs">{(r.risk_score * 100).toFixed(1)}%</span>
                      </td>
                      <td className="px-4 py-2">
                        <RiskBadge classification={r.classification} />
                      </td>
                      <td className="px-4 py-2 text-xs text-gray-500">{r.model_version}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
