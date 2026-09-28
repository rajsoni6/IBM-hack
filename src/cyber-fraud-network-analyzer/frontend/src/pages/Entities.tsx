/**
 * pages/Entities.tsx
 * Entity browser with type filter and risk score display.
 */
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import RiskBadge from '../components/RiskBadge'
import { listEntities } from '../api/entities'

const DEFAULT_CASE = 'case_001'
const ENTITY_TYPES = ['ALL', 'PERSON', 'VICTIM', 'BANK_ACCOUNT', 'PHONE', 'SIM', 'DEVICE', 'UPI_ID']

interface EntityData {
  entity_id: string
  type: string
  value: string
  label: string
  confidence: number
  risk_score: number
}

export default function Entities() {
  const [entities, setEntities] = useState<EntityData[]>([])
  const [loading, setLoading]   = useState(true)
  const [error,   setError]     = useState<string | null>(null)
  const [caseId,  setCaseId]    = useState(DEFAULT_CASE)
  const [filter,  setFilter]    = useState('ALL')
  const [search,  setSearch]    = useState('')

  useEffect(() => {
    setLoading(true)
    listEntities(caseId)
      .then((r) => {
        const nodes = r.nodes.map((n: any) => n.data as EntityData)
        setEntities(nodes)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [caseId])

  const visible = entities.filter((e) => {
    if (filter !== 'ALL' && e.type !== filter) return false
    if (search && !e.value?.toLowerCase().includes(search.toLowerCase()) &&
        !e.label?.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div>
      <PageHeader
        title="Entities"
        subtitle="Browse and filter extracted entities"
      />
      <div className="px-8 py-6 space-y-5">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">⚠ {error}</div>
        )}

        {/* Filters */}
        <div className="card p-4 flex flex-wrap gap-3 items-center">
          <div>
            <label className="text-xs font-medium text-gray-500 mr-2">Case ID</label>
            <input
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-40"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 mr-2">Search</label>
            <input
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-48"
              placeholder="Name, account…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex gap-1 flex-wrap">
            {ENTITY_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setFilter(t)}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                  filter === t
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="card">
          <div className="p-4 border-b border-gray-100">
            <p className="text-sm text-gray-500">
              {loading ? 'Loading…' : `${visible.length} entity${visible.length !== 1 ? 'ies' : 'y'}`}
            </p>
          </div>
          {loading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse text-sm">Loading entities…</div>
          ) : visible.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">No entities found.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-100">
                  <tr>
                    {['Entity', 'Type', 'Value', 'Confidence', 'Risk Score'].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {visible.map((e) => (
                    <tr key={e.entity_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-800">{e.label || e.value}</p>
                        <p className="text-xs text-gray-400">{e.entity_id}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className="badge badge-info">{e.type}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-600 font-mono text-xs">{e.value}</td>
                      <td className="px-4 py-3 text-gray-600">
                        {e.confidence !== undefined ? `${(e.confidence * 100).toFixed(0)}%` : '—'}
                      </td>
                      <td className="px-4 py-3">
                        {e.risk_score !== undefined ? (
                          <div className="flex items-center gap-2">
                            <div className="flex-1 bg-gray-200 rounded-full h-1.5 w-16">
                              <div
                                className="bg-red-500 h-1.5 rounded-full"
                                style={{ width: `${(e.risk_score * 100).toFixed(0)}%` }}
                              />
                            </div>
                            <RiskBadge score={e.risk_score} />
                          </div>
                        ) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
