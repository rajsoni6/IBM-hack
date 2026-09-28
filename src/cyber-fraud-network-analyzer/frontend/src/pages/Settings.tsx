/**
 * pages/Settings.tsx
 * Application settings: model info, data directory, AI provider.
 */
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import { getHealth, type HealthResponse } from '../api/health'

export default function Settings() {
  const [health, setHealth] = useState<HealthResponse | null>(null)

  useEffect(() => {
    getHealth().then(setHealth).catch(() => null)
  }, [])

  return (
    <div>
      <PageHeader title="Settings" subtitle="Application configuration and system information" />

      <div className="px-8 py-6 space-y-5 max-w-3xl">
        {/* Backend info */}
        <div className="card p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-700">Backend</h2>
          <div className="grid grid-cols-2 gap-y-2 text-sm">
            <span className="text-gray-500">API Base URL</span>
            <span className="font-mono text-gray-800">http://localhost:5000</span>
            <span className="text-gray-500">Service</span>
            <span className="text-gray-800">{health?.service ?? '—'}</span>
            <span className="text-gray-500">Version</span>
            <span className="text-gray-800">{health?.version ?? '—'}</span>
            <span className="text-gray-500">Phase</span>
            <span className="text-gray-800">{health?.phase ?? '—'}</span>
            <span className="text-gray-500">Environment</span>
            <span className="text-gray-800">{health?.environment ?? '—'}</span>
          </div>
        </div>

        {/* AI Provider */}
        <div className="card p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-700">AI Provider</h2>
          <div className="grid grid-cols-2 gap-y-2 text-sm">
            <span className="text-gray-500">Active Provider</span>
            <span className="font-medium text-gray-800">{health?.ai_provider ?? '—'}</span>
            <span className="text-gray-500">Summary Mode</span>
            <span className="text-gray-800">Mock (deterministic, no hallucination)</span>
            <span className="text-gray-500">Override</span>
            <span className="text-gray-400 text-xs">Set AI_PROVIDER=watsonx in backend .env</span>
          </div>
        </div>

        {/* ML Model */}
        <div className="card p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-700">ML Model</h2>
          <div className="grid grid-cols-2 gap-y-2 text-sm">
            <span className="text-gray-500">Model Version</span>
            <span className="text-gray-800">fraud-model-v1</span>
            <span className="text-gray-500">Algorithm</span>
            <span className="text-gray-800">Logistic Regression (best by PR-AUC)</span>
            <span className="text-gray-500">Features</span>
            <span className="text-gray-800">19 account-level features</span>
            <span className="text-gray-500">Training Data</span>
            <span className="text-gray-800">10,000 accounts · 90,266 transactions</span>
            <span className="text-gray-500">Class Balance</span>
            <span className="text-gray-800">266 fraud / 9,734 normal (2.66%)</span>
            <span className="text-gray-500">Artifacts Path</span>
            <span className="font-mono text-xs text-gray-600">models/</span>
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800">
            Retrain: run <code className="font-mono bg-amber-100 px-1 rounded">python scripts/train_model.py</code> from project root
          </div>
        </div>

        {/* Data directory */}
        <div className="card p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-700">Data Directory</h2>
          <div className="grid grid-cols-2 gap-y-2 text-sm">
            {[
              ['Cases',         'data/cases/cases.json'],
              ['Entities',      'data/entities/entities.json'],
              ['Relationships', 'data/relationships/relationships.json'],
              ['Evidence',      'data/evidence/evidence.json'],
              ['Reports',       'data/reports/'],
              ['Predictions',   'data/predictions/predictions.json'],
              ['Sample Data',   'data/sample/'],
            ].map(([label, path]) => (
              <>
                <span key={`${label}-l`} className="text-gray-500">{label}</span>
                <span key={`${label}-v`} className="font-mono text-xs text-gray-600">{path}</span>
              </>
            ))}
          </div>
        </div>

        {/* Phases */}
        {health && (
          <div className="card p-5 space-y-3">
            <h2 className="text-sm font-semibold text-gray-700">System Phases</h2>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <p className="font-medium text-green-600 mb-1">✓ Complete</p>
                <ul className="space-y-0.5 text-gray-600">
                  {health.phases_complete.map((p) => (
                    <li key={p} className="capitalize">{p.replace(/-/g, ' ')}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="font-medium text-gray-400 mb-1">○ Pending</p>
                <ul className="space-y-0.5 text-gray-400">
                  {health.phases_pending.map((p) => (
                    <li key={p} className="capitalize">{p.replace(/-/g, ' ')}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
