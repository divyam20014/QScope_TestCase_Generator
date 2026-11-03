import { api } from '@/lib/api'
import type { Project } from '@/types/project'
import { useQuery } from '@tanstack/react-query'
import { createContext, useContext, useState, type ReactNode } from 'react'

const STORAGE_KEY = 'qscope-active-project-id'

interface ActiveProjectContextValue {
  projectId: string | null
  setProjectId: (id: string | null) => void
  projects: Project[]
  isLoading: boolean
}

const ActiveProjectContext = createContext<ActiveProjectContextValue | null>(null)

function readStoredProjectId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function ActiveProjectProvider({ children }: { children: ReactNode }) {
  const [explicitProjectId, setExplicitProjectId] = useState<string | null>(readStoredProjectId)

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => api.get<Project[]>('/projects'),
  })

  // Fall back to the first available project when nothing (valid) is stored,
  // derived at render time rather than via an effect + extra re-render.
  const storedIsValid = !!explicitProjectId && projects.some((p) => p.id === explicitProjectId)
  const projectId = storedIsValid ? explicitProjectId : (projects[0]?.id ?? null)

  function setProjectId(id: string | null) {
    setExplicitProjectId(id)
    try {
      if (id) localStorage.setItem(STORAGE_KEY, id)
      else localStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore storage failures
    }
  }

  return (
    <ActiveProjectContext.Provider value={{ projectId, setProjectId, projects, isLoading }}>
      {children}
    </ActiveProjectContext.Provider>
  )
}

export function useActiveProject() {
  const ctx = useContext(ActiveProjectContext)
  if (!ctx) throw new Error('useActiveProject must be used within ActiveProjectProvider')
  return ctx
}
