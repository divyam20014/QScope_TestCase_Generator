import { cn } from '@/lib/utils'
import {
  BarChart3,
  FileCheck2,
  FileText,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  ListChecks,
  Settings,
  Sparkles,
  Table2,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/projects', label: 'Projects', icon: FlaskConical },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/requirement-analysis', label: 'Requirement Analysis', icon: ListChecks },
  { to: '/test-generator', label: 'Test Case Generator', icon: Sparkles },
  { to: '/test-repository', label: 'Test Case Repository', icon: Table2 },
  { to: '/coverage', label: 'Coverage Analysis', icon: Gauge },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/ai-configuration', label: 'AI Configuration', icon: FileCheck2 },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Sidebar() {
  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="flex h-14 items-center gap-2 border-b border-[var(--color-border)] px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--color-accent)] text-sm font-bold text-[var(--color-accent-contrast)]">
          Q
        </div>
        <span className="text-sm font-semibold text-[var(--color-text)]">QScope</span>
      </div>
      <nav className="flex-1 overflow-y-auto p-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-[var(--color-accent)]/10 text-[var(--color-accent)]'
                  : 'text-[var(--color-text-muted)] hover:bg-[var(--color-border)]/40 hover:text-[var(--color-text)]',
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
