import { ProjectSwitcher } from '@/components/layout/ProjectSwitcher'
import { applyTheme, getInitialTheme, type Theme } from '@/components/layout/theme'
import { Moon, Search, Sun } from 'lucide-react'
import { useLayoutEffect, useState } from 'react'

export function Topbar() {
  const [theme, setTheme] = useState<Theme>(() => getInitialTheme())

  useLayoutEffect(() => {
    applyTheme(theme)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function toggleTheme() {
    const next: Theme = theme === 'light' ? 'dark' : 'light'
    setTheme(next)
    applyTheme(next)
  }

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4">
      <div className="flex max-w-md flex-1 items-center gap-2 rounded-md border border-[var(--color-border)] px-3 py-1.5">
        <Search className="h-4 w-4 text-[var(--color-text-muted)]" />
        <input
          placeholder="Search coming soon..."
          disabled
          className="w-full bg-transparent text-sm outline-none placeholder:text-[var(--color-text-muted)]"
        />
      </div>
      <div className="flex items-center gap-3">
        <ProjectSwitcher />
        <button
          onClick={toggleTheme}
          className="flex h-9 w-9 items-center justify-center rounded-md text-[var(--color-text-muted)] hover:bg-[var(--color-border)]/40"
          aria-label="Toggle theme"
        >
          {theme === 'light' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
        </button>
      </div>
    </header>
  )
}
