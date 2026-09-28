/**
 * components/Layout.tsx
 * Root shell: sidebar navigation + main content outlet.
 */
import { NavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/dashboard',    label: 'Dashboard',       icon: '⊞',  group: 'main' },
  { to: '/cases',        label: 'Cases',            icon: '📁', group: 'main' },
  { to: '/entities',     label: 'Entities',         icon: '👤', group: 'intel' },
  { to: '/graph',        label: 'Network Graph',    icon: '🕸', group: 'intel' },
  { to: '/transactions', label: 'Transactions',     icon: '💳', group: 'intel' },
  { to: '/patterns',     label: 'Patterns',         icon: '🔍', group: 'intel' },
  { to: '/roles',        label: 'Roles',            icon: '🎭', group: 'intel' },
  { to: '/timeline',     label: 'Timeline',         icon: '📅', group: 'invest' },
  { to: '/evidence',     label: 'Evidence',         icon: '🔗', group: 'invest' },
  { to: '/ml',           label: 'ML Prediction',    icon: '🤖', group: 'ml' },
  { to: '/ai-brief',     label: 'AI Brief',         icon: '📄', group: 'ml' },
  { to: '/settings',     label: 'Settings',         icon: '⚙',  group: 'sys' },
]

const GROUP_LABELS: Record<string, string> = {
  main:   'Overview',
  intel:  'Intelligence',
  invest: 'Investigation',
  ml:     'ML & AI',
  sys:    'System',
}

export default function Layout() {
  const groups = [...new Set(NAV_ITEMS.map((n) => n.group))]

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="flex flex-col w-56 shrink-0 bg-brand-900 text-white overflow-y-auto">
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 py-4 border-b border-white/10 shrink-0">
          <span className="text-xl">🔍</span>
          <div>
            <p className="text-sm font-semibold leading-tight">Cyber Fraud</p>
            <p className="text-xs text-blue-200 leading-tight">Network Analyzer</p>
          </div>
        </div>

        {/* Nav links by group */}
        <nav className="flex flex-col px-2 py-3 flex-1 gap-0">
          {groups.map((group) => (
            <div key={group} className="mb-2">
              <p className="text-xs font-semibold text-blue-300/60 uppercase tracking-wider px-3 mb-1 mt-2">
                {GROUP_LABELS[group]}
              </p>
              {NAV_ITEMS.filter((n) => n.group === group).map(({ to, label, icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors
                     ${isActive
                       ? 'bg-brand-600 text-white font-medium'
                       : 'text-blue-100 hover:bg-white/10 hover:text-white'}`
                  }
                >
                  <span className="text-sm shrink-0">{icon}</span>
                  <span className="truncate">{label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-white/10 shrink-0">
          <p className="text-xs text-blue-300">Phase 9 — Full Dashboard</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-gray-50">
        <Outlet />
      </main>
    </div>
  )
}
