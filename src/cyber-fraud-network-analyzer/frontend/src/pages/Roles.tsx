/**
 * pages/Roles.tsx
 * Network role analysis with distribution chart and role table.
 */
import { useEffect, useState } from 'react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import PageHeader from '../components/PageHeader'
import RiskBadge from '../components/RiskBadge'
import { getRoles, runRoleAnalysis, type RolesResponse, type RoleEntry } from '../api/patterns'

const COLORS = ['#3b82f6', '#ef4444', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']

const ROLE_EXPLANATIONS: Record<string, string> = {
  'Money Mule':        'Receives and forwards fraudulent funds to obscure the trail.',
  'Central Hub':       'High-connectivity node that coordinates multiple transactions.',
  'Source':            'Originates the financial flow; potential perpetrator account.',
  'Sink':              'Final destination of funds; may be cash-out or escape account.',
  'Intermediary':      'Passes funds between other accounts in a layering scheme.',
  'Victim':            'Account that was defrauded; initial source of funds.',
  'Peripheral':        'Low connectivity; possibly legitimate or newly added account.',
}

export default function Roles() {
  const [data,    setData]    = useState<RolesResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const [caseId,  setCaseId]  = useState('case_001')

  const load = (id: string) => {
    setLoading(true)
    getRoles(id)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  const runAnalysis = () => {
    setRunning(true)
    runRoleAnalysis(caseId)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setRunning(false))
  }

  useEffect(() => load(caseId), [caseId])

  const chartData = data
    ? Object.entries(data.role_summary).map(([name, value]) => ({ name, value }))
    : []

  return (
    <div>
      <PageHeader
        title="Network Roles"
        subtitle="Role classification of entities in the fraud network"
        actions={
          <div className="flex gap-2 items-center">
            <input
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-40"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              placeholder="Case ID"
            />
            <button className="btn-primary text-sm" onClick={runAnalysis} disabled={running}>
              {running ? 'Analyzing…' : '▶ Run Analysis'}
            </button>
          </div>
        }
      />
      <div className="px-8 py-6 space-y-5">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">⚠ {error}</div>
        )}

        {loading ? (
          <div className="card p-8 text-center text-gray-400 animate-pulse text-sm">Loading roles…</div>
        ) : !data ? (
          <div className="card p-8 text-center text-gray-400 text-sm">
            <p className="text-3xl mb-3">🎭</p>
            <p>No role analysis found. Click Run Analysis to start.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Pie chart */}
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">Role Distribution</h2>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={chartData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
              <p className="text-xs text-center text-gray-400 mt-2">
                {data.total_entities} entities across {chartData.length} roles
              </p>
            </div>

            {/* Role explanations */}
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">Role Guide</h2>
              <div className="space-y-3">
                {Object.entries(ROLE_EXPLANATIONS).map(([role, desc]) => (
                  <div key={role}>
                    <p className="text-xs font-semibold text-gray-700">{role}</p>
                    <p className="text-xs text-gray-500">{desc}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Entity table */}
            <div className="card lg:col-span-1">
              <div className="p-4 border-b border-gray-100">
                <p className="text-sm font-semibold text-gray-700">Top Entities by Risk</p>
              </div>
              <div className="overflow-y-auto max-h-96">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs text-gray-500">Entity</th>
                      <th className="px-4 py-2 text-left text-xs text-gray-500">Role</th>
                      <th className="px-4 py-2 text-left text-xs text-gray-500">Risk</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.roles
                      .slice()
                      .sort((a: RoleEntry, b: RoleEntry) => (b.risk_score ?? 0) - (a.risk_score ?? 0))
                      .slice(0, 20)
                      .map((r: RoleEntry) => (
                        <tr key={r.entity_id} className="hover:bg-gray-50">
                          <td className="px-4 py-2 text-xs font-mono text-gray-700">
                            {r.entity_id}
                          </td>
                          <td className="px-4 py-2 text-xs text-gray-600">
                            {r.primary_role ?? '—'}
                          </td>
                          <td className="px-4 py-2">
                            <RiskBadge score={r.risk_score} />
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
