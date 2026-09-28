/**
 * pages/Evidence.tsx
 * Evidence management with source chain display.
 */
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import EvidenceChain from '../components/EvidenceChain'
import { listEvidence, getEvidence, type EvidenceRecord } from '../api/evidence'

export default function Evidence() {
  const [records,  setRecords]  = useState<EvidenceRecord[]>([])
  const [selected, setSelected] = useState<EvidenceRecord | null>(null)
  const [loading,  setLoading]  = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error,    setError]    = useState<string | null>(null)
  const [caseId,   setCaseId]   = useState('case_001')
  const [filter,   setFilter]   = useState('')

  const load = (id: string) => {
    setLoading(true)
    setSelected(null)
    listEvidence(id)
      .then((r) => setRecords(r.evidence))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => load(caseId), [caseId])

  const handleSelect = (rec: EvidenceRecord) => {
    setDetailLoading(true)
    getEvidence(caseId, rec.evidence_id)
      .then(setSelected)
      .catch(() => setSelected(rec))
      .finally(() => setDetailLoading(false))
  }

  const visible = filter
    ? records.filter((r) =>
        r.type?.toLowerCase().includes(filter.toLowerCase()) ||
        r.description?.toLowerCase().includes(filter.toLowerCase())
      )
    : records

  return (
    <div>
      <PageHeader title="Evidence" subtitle="Manage and review investigation evidence records" />

      <div className="px-8 py-6 space-y-5">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">⚠ {error}</div>
        )}

        {/* Controls */}
        <div className="card p-4 flex gap-3 items-center">
          <div>
            <label className="text-xs font-medium text-gray-500 mr-2">Case ID</label>
            <input
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-40"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') load(caseId) }}
            />
            <button className="ml-2 btn-secondary text-xs py-1" onClick={() => load(caseId)}>
              Load
            </button>
          </div>
          <input
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-56"
            placeholder="Filter by type or description…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Evidence list */}
          <div className="card">
            <div className="p-4 border-b border-gray-100">
              <p className="text-sm font-semibold text-gray-700">
                {loading ? 'Loading…' : `${visible.length} record${visible.length !== 1 ? 's' : ''}`}
              </p>
            </div>
            {loading ? (
              <div className="p-8 text-center text-gray-400 animate-pulse text-sm">Loading evidence…</div>
            ) : visible.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-sm">No evidence records found.</div>
            ) : (
              <div className="divide-y divide-gray-100 max-h-[600px] overflow-y-auto">
                {visible.map((rec) => (
                  <button
                    key={rec.evidence_id}
                    className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                      selected?.evidence_id === rec.evidence_id ? 'bg-blue-50' : ''
                    }`}
                    onClick={() => handleSelect(rec)}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-800">{rec.type || rec.evidence_id}</p>
                        <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{rec.description}</p>
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0 ml-2">
                        {rec.is_verified && (
                          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                            ✓ Verified
                          </span>
                        )}
                        <span className="text-xs text-gray-300">
                          {rec.timestamp ? new Date(rec.timestamp).toLocaleDateString() : ''}
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Evidence detail / chain */}
          <div className="card p-5">
            {detailLoading ? (
              <div className="text-sm text-gray-400 animate-pulse">Loading chain…</div>
            ) : selected ? (
              <>
                <div className="mb-4">
                  <h2 className="text-sm font-semibold text-gray-700">{selected.type || 'Evidence Detail'}</h2>
                  <p className="text-xs text-gray-400">{selected.evidence_id}</p>
                </div>
                <EvidenceChain evidence={selected} />
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-48 text-gray-400">
                <p className="text-3xl mb-2">🔗</p>
                <p className="text-sm">Select an evidence record to view its chain</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
