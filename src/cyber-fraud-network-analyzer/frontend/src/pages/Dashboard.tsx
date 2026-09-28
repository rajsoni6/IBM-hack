/**
 * pages/Dashboard.tsx
 * Main overview dashboard with workflow stepper, stats, and recent cases.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getHealth, type HealthResponse } from '../api/health'
import { listCases, type Case } from '../api/cases'
import PageHeader from '../components/PageHeader'
import StatCard from '../components/StatCard'
import WorkflowStepper from '../components/WorkflowStepper'
import StatusBadge from '../components/StatusBadge'

const SEVERITY_COLOR: Record<string, string> = {
  critical: 'bg-red-100 text-red-700',
  high:     'bg-orange-100 text-orange-700',
  medium:   'bg-yellow-100 text-yellow-700',
  low:      'bg-blue-100 text-blue-700',
}

export default function Dashboard() {
  const [health,  setHealth]  = useState<HealthResponse | null>(null)
  const [cases,   setCases]   = useState<Case[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      getHealth().catch(() => null),
      listCases({ limit: 6 }).catch(() => ({ cases: [], total: 0, limit: 6, offset: 0 })),
    ]).then(([h, c]) => {
      setHealth(h)
      setCases(c.cases)
    }).catch((e: Error) => setError(e.message))
     .finally(() => setLoading(false))
  }, [])

  const totalCases     = cases.length
  const openCases      = cases.filter((c) => c.status === 'open' || c.status === 'under_investigation').length
  const criticalCases  = cases.filter((c) => c.severity === 'critical' || c.severity === 'high').length
  const totalLoss      = cases.reduce((s, c) => s + (c.total_loss_inr || 0), 0)

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="Cyber Fraud Network Analyzer — Investigation Overview"
        actions={
          <Link to="/cases" className="btn-primary text-sm">
            + New Case
          </Link>
        }
      />

      <div className="px-8 py-6 space-y-6">
        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
            ⚠ {error}
          </div>
        )}

        {/* Workflow Stepper */}
        <WorkflowStepper activeStep="report" />

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Cases"    value={loading ? '…' : totalCases}    icon="📁" />
          <StatCard label="Open / Active"  value={loading ? '…' : openCases}     icon="🔍" />
          <StatCard
            label="High / Critical"
            value={loading ? '…' : criticalCases}
            icon="🚨"
            trend={criticalCases > 0 ? `${criticalCases} urgent` : undefined}
            trendUp={criticalCases > 0}
          />
          <StatCard
            label="Est. Total Loss"
            value={loading ? '…' : `₹${(totalLoss / 1_00_000).toFixed(1)}L`}
            icon="💰"
          />
        </div>

        {/* Backend Health */}
        {health && (
          <div className="card p-5">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Backend Status
            </h2>
            <div className="flex flex-wrap gap-6 text-sm">
              <span className="flex items-center gap-2">
                <span className="text-gray-500">Status</span>
                <StatusBadge status={health.status} />
              </span>
              <span className="flex items-center gap-2">
                <span className="text-gray-500">Service</span>
                <span className="font-medium">{health.service}</span>
              </span>
              <span className="flex items-center gap-2">
                <span className="text-gray-500">AI Provider</span>
                <StatusBadge status="info" label={health.ai_provider} />
              </span>
              <span className="flex items-center gap-2">
                <span className="text-gray-500">Phase</span>
                <span className="font-medium">{health.phase}</span>
              </span>
            </div>
          </div>
        )}

        {/* Quick Actions */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { to: '/cases',      label: 'Manage Cases',    icon: '📁', desc: 'View and create fraud cases' },
            { to: '/graph',      label: 'Network Graph',   icon: '🕸', desc: 'Visualise entity relationships' },
            { to: '/ml',         label: 'ML Prediction',   icon: '🤖', desc: 'Run fraud risk predictions' },
            { to: '/ai-brief',   label: 'Generate FIR',    icon: '📄', desc: 'AI-drafted case brief' },
          ].map(({ to, label, icon, desc }) => (
            <Link
              key={to}
              to={to}
              className="card p-4 hover:bg-gray-50 transition-colors group block"
            >
              <div className="text-2xl mb-2">{icon}</div>
              <p className="text-sm font-semibold text-gray-800 group-hover:text-blue-700">{label}</p>
              <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
            </Link>
          ))}
        </div>

        {/* Recent Cases */}
        <div className="card">
          <div className="flex items-center justify-between p-5 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700">Recent Cases</h2>
            <Link to="/cases" className="text-xs text-blue-600 hover:underline">
              View all →
            </Link>
          </div>
          {loading ? (
            <div className="p-5 text-sm text-gray-400 animate-pulse">Loading…</div>
          ) : cases.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">
              No cases yet. <Link to="/cases" className="text-blue-600 hover:underline">Create one</Link>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {cases.slice(0, 6).map((c) => (
                <div key={c.id} className="flex items-center px-5 py-3 hover:bg-gray-50 transition-colors">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{c.title}</p>
                    <p className="text-xs text-gray-400">
                      {c.jurisdiction} · {c.assigned_to || 'Unassigned'} · {c.fraud_pattern?.replace(/_/g, ' ')}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        SEVERITY_COLOR[c.severity] ?? 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {c.severity}
                    </span>
                    <StatusBadge status={c.status} label={c.status.replace(/_/g, ' ')} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
