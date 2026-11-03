import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Input, Textarea } from '@/components/ui/input'
import { api } from '@/lib/api'
import type { Project, ProjectCreatePayload } from '@/types/project'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, Copy, Plus, RotateCcw, Trash2 } from 'lucide-react'
import { useState } from 'react'

export function ProjectsPage() {
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState<ProjectCreatePayload>({ name: '', description: '', business_domain: '' })

  const { data: projects, isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: () => api.get<Project[]>('/projects'),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['projects'] })

  const createMutation = useMutation({
    mutationFn: (payload: ProjectCreatePayload) => api.post<Project>('/projects', payload),
    onSuccess: () => {
      invalidate()
      setCreateOpen(false)
      setForm({ name: '', description: '', business_domain: '' })
    },
  })

  const archiveMutation = useMutation({
    mutationFn: (id: string) => api.post<Project>(`/projects/${id}/archive`),
    onSuccess: invalidate,
  })

  const restoreMutation = useMutation({
    mutationFn: (id: string) => api.post<Project>(`/projects/${id}/restore`),
    onSuccess: invalidate,
  })

  const duplicateMutation = useMutation({
    mutationFn: (id: string) => api.post<Project>(`/projects/${id}/duplicate`),
    onSuccess: invalidate,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/projects/${id}`),
    onSuccess: invalidate,
  })

  function handleCreate() {
    if (!form.name.trim()) return
    createMutation.mutate(form)
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-[var(--color-text)]">Projects</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4" /> New Project
        </Button>
      </div>

      {isLoading && <p className="text-sm text-[var(--color-text-muted)]">Loading projects...</p>}
      {error && (
        <p className="text-sm text-[var(--color-danger)]">
          Failed to load projects. Is the backend running on port 8000?
        </p>
      )}

      {projects && projects.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-[var(--color-text-muted)]">
            No projects yet. Create your first QA project to get started.
          </CardContent>
        </Card>
      )}

      {projects && projects.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((project: Project) => (
            <Card key={project.id}>
              <CardContent>
                <div className="mb-2 flex items-start justify-between">
                  <h3 className="font-semibold text-[var(--color-text)]">{project.name}</h3>
                  <Badge tone={project.status === 'active' ? 'success' : 'neutral'}>
                    {project.status}
                  </Badge>
                </div>
                {project.description && (
                  <p className="mb-2 text-sm text-[var(--color-text-muted)]">{project.description}</p>
                )}
                {project.business_domain && (
                  <p className="mb-3 text-xs text-[var(--color-text-muted)]">
                    Domain: {project.business_domain}
                  </p>
                )}
                <div className="mb-4 grid grid-cols-3 gap-2 text-center text-xs text-[var(--color-text-muted)]">
                  <div>
                    <div className="text-sm font-semibold text-[var(--color-text)]">
                      {project.document_count}
                    </div>
                    Docs
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-[var(--color-text)]">
                      {project.requirement_count}
                    </div>
                    Reqs
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-[var(--color-text)]">
                      {project.test_case_count}
                    </div>
                    Tests
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => duplicateMutation.mutate(project.id)}
                    title="Duplicate"
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </Button>
                  {project.status === 'active' ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => archiveMutation.mutate(project.id)}
                      title="Archive"
                    >
                      <Archive className="h-3.5 w-3.5" />
                    </Button>
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => restoreMutation.mutate(project.id)}
                      title="Restore"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                    </Button>
                  )}
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => {
                      if (confirm(`Delete project "${project.name}"? This cannot be undone.`)) {
                        deleteMutation.mutate(project.id)
                      }
                    }}
                    title="Delete"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} title="New Project">
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
              Name
            </label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Loan Origination QA"
              autoFocus
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
              Description
            </label>
            <Textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
              Business Domain
            </label>
            <Input
              value={form.business_domain}
              onChange={(e) => setForm({ ...form, business_domain: e.target.value })}
              placeholder="e.g. Banking, Healthcare"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={!form.name.trim() || createMutation.isPending}>
              {createMutation.isPending ? 'Creating...' : 'Create'}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
