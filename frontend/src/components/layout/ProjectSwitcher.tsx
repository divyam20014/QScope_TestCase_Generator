import { useActiveProject } from '@/lib/active-project'

export function ProjectSwitcher() {
  const { projectId, setProjectId, projects, isLoading } = useActiveProject()

  if (isLoading) return null

  if (projects.length === 0) {
    return <span className="text-xs text-[var(--color-text-muted)]">No projects yet</span>
  }

  return (
    <select
      value={projectId ?? ''}
      onChange={(e) => setProjectId(e.target.value || null)}
      className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-sm text-[var(--color-text)]"
    >
      {projects.map((project) => (
        <option key={project.id} value={project.id}>
          {project.name}
        </option>
      ))}
    </select>
  )
}
