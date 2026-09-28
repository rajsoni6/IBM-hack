/**
 * pages/Cases.tsx
 * Full case management: list, create, detail.
 */
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import StatusBadge from '../components/StatusBadge'
import { listCases, createCase, type Case, type CreateCasePayload } from '../api/cases'

const SEVERITY_COLOR: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 border-red-200',
  high:     'bg-orange-100 text-orange-700 border-orange-200',
  medium:   'bg-yellow-100 text-yellow-700 border-yellow-200',
  low:      'bg-blue-100 text-blue-700 border-blue-200',
}

const FRAUD_PATTERNS = [
  'sim_swap', 'mule_network', 'transaction_layering',
  'shared_device', 'shared_sim', 'communication_hub',
  'rapid_multi_hop', 'legitimate', 'unknown',
]

export default function Cases() {
  const [cases,   setCases]   = useState<Case[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form,    setForm]    = useState<CreateCasePayload>({
    title: '', description: '', fraud_pattern: 'unknown',
    severity: 'medium', status: 'open', jurisdiction: '', assigned_to: '',
    total_loss_inr: 0,
  })

  const load = () => {
    setLoading(true)
    listCases({ limit: 100 })
      .then((r) => setCases(r.cases))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleCreate = async () => {
    if (!form.title.trim()) return
    setCreating(true)
    try {
      await createCase(form)
      setShowForm(false)
      setForm({ title: '', description: '', fraud_pattern: 'unknown',
                severity: 'medium', status: 'open', jurisdiction: '',
                assigned_to: '', total_loss_inr: 0 })
      load()
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Cases"
        subtitle="Manage and investigate fraud cases"
        actions={
          <button className="btn-primary text-sm" onClick={() => setShowForm(!showForm)}>
            {showForm ? '✕ Cancel' : '+ New Case'}
          </button>
        }
      />

      <div className="px-8 py-6 space-y-5">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
            ⚠ {error}
          </div>
        )}

        {/* Create Form */}
        {showForm && (
          <div className="card p-6 space-y-4">
            <h2 className="text-sm font-semibold text-gray-700">New Case</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Title *</label>
                <input
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="Brief description of the case"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Fraud Pattern</label>
                <select
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.fraud_pattern}
                  onChange={(e) => setForm({ ...form, fraud_pattern: e.target.value })}
                >
                  {FRAUD_PATTERNS.map((p) => (
                    <option key={p} value={p}>{p.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Severity</label>
                <select
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.severity}
                  onChange={(e) => setForm({ ...form, severity: e.target.value })}
                >
                  {['critical', 'high', 'medium', 'low'].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Jurisdiction</label>
                <input
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.jurisdiction}
                  onChange={(e) => setForm({ ...form, jurisdiction: e.target.value })}
                  placeholder="e.g. Mumbai"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Assigned To</label>
                <input
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.assigned_to}
                  onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}
                  placeholder="e.g. IO-Singh"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Est. Loss (INR)</label>
                <input
                  type="number"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.total_loss_inr}
                  onChange={(e) => setForm({ ...form, total_loss_inr: Number(e.target.value) })}
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Description</label>
              <textarea
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={3}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Case details…"
              />
            </div>
            <div className="flex gap-3">
              <button
                className="btn-primary text-sm"
                onClick={handleCreate}
                disabled={creating || !form.title.trim()}
              >
                {creating ? 'Creating…' : 'Create Case'}
              </button>
              <button className="btn-secondary text-sm" onClick={() => setShowForm(false)}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Cases Table */}
        <div className="card">
          <div className="p-5 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">
              {loading ? 'Loading…' : `${cases.length} case${cases.length !== 1 ? 's' : ''}`}
            </h2>
          </div>
          {loading ? (
            <div className="p-8 text-center text-gray-400 text-sm animate-pulse">Loading cases…</div>
          ) : cases.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">
              No cases found. Create the first one using the button above.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-100">
                  <tr>
                    {['Title', 'Pattern', 'Severity', 'Status', 'Jurisdiction', 'Loss (₹)', 'Assigned'].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {cases.map((c) => (
                    <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900">{c.title}</p>
                        <p className="text-xs text-gray-400">{c.id}</p>
                      </td>
                      <td className="px-4 py-3 text-gray-600 capitalize">
                        {c.fraud_pattern?.replace(/_/g, ' ')}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${SEVERITY_COLOR[c.severity] ?? ''}`}>
                          {c.severity}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={c.status} label={c.status.replace(/_/g, ' ')} />
                      </td>
                      <td className="px-4 py-3 text-gray-600">{c.jurisdiction || '—'}</td>
                      <td className="px-4 py-3 text-gray-600">
                        {c.total_loss_inr ? `₹${c.total_loss_inr.toLocaleString()}` : '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{c.assigned_to || '—'}</td>
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
