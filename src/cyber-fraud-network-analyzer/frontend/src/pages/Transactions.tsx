/**
 * pages/Transactions.tsx
 * Transaction explorer with risk indicators.
 */
import { useState } from 'react'
import PageHeader from '../components/PageHeader'

export default function Transactions() {
  const [filter, setFilter] = useState<'all' | 'flagged'>('all')
  const [search, setSearch] = useState('')

  return (
    <div>
      <PageHeader title="Transactions" subtitle="Explore transaction records and risk indicators" />

      <div className="px-8 py-6 space-y-5">
        {/* Filters */}
        <div className="card p-4 flex gap-4 items-center">
          <input
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-56"
            placeholder="Search account or transaction ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="flex gap-2">
            {(['all', 'flagged'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                  filter === f
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {f === 'all' ? 'All' : '🚩 Flagged'}
              </button>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="p-4 border-b border-gray-100">
            <p className="text-sm text-gray-500">
              Transaction data is available via the Network Graph and Pattern Analysis pages.
              Navigate to <strong>/graph</strong> or <strong>/patterns</strong> to inspect per-case transactions.
            </p>
          </div>
          <div className="p-8 text-center text-gray-400">
            <p className="text-4xl mb-3">💳</p>
            <p className="text-sm font-medium">Load transactions via the Graph page</p>
            <p className="text-xs text-gray-400 mt-1">
              Select a case in Graph → Pattern Analysis to see transaction-level data
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
