import { NavLink } from 'react-router-dom'
import { cn } from '../../components/ui/utils'

const navGroups = [
  {
    label: 'Underwriting',
    items: [
      { to: '/underwriting/workbench', label: 'Submission Workbench' },
      { to: '/underwriting/rules', label: 'Appetite & Referral Rules' },
      { to: '/underwriting/findings', label: 'Referrals' },
      { to: '/underwriting', label: 'AI Underwriting' },
    ],
  },
  {
    label: 'Portfolio',
    items: [
      { to: '/ingestion', label: 'Ingestion' },
      { to: '/exposure-versions', label: 'Exposure Versions' },
      { to: '/exceptions', label: 'Exceptions' },
      { to: '/hazard-datasets', label: 'Hazard Datasets' },
      { to: '/overlays', label: 'Overlays' },
      { to: '/rollups', label: 'Rollups' },
      { to: '/threshold-rules', label: 'Threshold Rules' },
      { to: '/breaches', label: 'Breaches' },
    ],
  },
  {
    label: 'Governance',
    items: [
      { to: '/runs', label: 'Runs' },
      { to: '/audit-log', label: 'Audit Log' },
    ],
  },
]

export function Sidebar() {
  return (
    <aside className="w-64 flex-shrink-0 border-r border-slate-200 bg-white">
      <div className="p-4 text-lg font-semibold">Aegis Control Tower</div>
      <nav className="space-y-4 p-2">
        {navGroups.map((group) => (
          <div key={group.label} className="space-y-1">
            <div className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">{group.label}</div>
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'block rounded-md px-3 py-2 text-sm font-medium hover:bg-slate-100',
                    isActive ? 'bg-blue-50 text-blue-700' : 'text-slate-700'
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  )
}
