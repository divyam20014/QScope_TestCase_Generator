import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useActiveProject } from '@/lib/active-project'
import { api } from '@/lib/api'
import type { DocumentRecord } from '@/types/document'
import type { ClassificationState, ClarificationItem, Requirement } from '@/types/requirement'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

const STATE_TONE: Record<ClassificationState, 'success' | 'warning' | 'danger' | 'neutral'> = {
  clear: 'success',
  partial: 'warning',
  ambiguous: 'warning',
  conflicting: 'danger',
  missing: 'danger',
  not_testable: 'neutral',
}

export function RequirementAnalysisPage() {
  const { projectId, projects, isLoading: projectsLoading } = useActiveProject()
  const queryClient = useQueryClient()
  const [extractError, setExtractError] = useState<string | null>(null)
  const [resolvingId, setResolvingId] = useState<string | null>(null)
  const [resolutionNote, setResolutionNote] = useState('')

  const { data: requirements, isLoading } = useQuery({
    queryKey: ['requirements', projectId],
    queryFn: () => api.get<Requirement[]>(`/projects/${projectId}/requirements`),
    enabled: !!projectId,
  })

  const { data: documents } = useQuery({
    queryKey: ['documents', projectId],
    queryFn: () => api.get<DocumentRecord[]>(`/projects/${projectId}/documents`),
    enabled: !!projectId,
  })

  const { data: clarifications } = useQuery({
    queryKey: ['clarifications', projectId],
    queryFn: () => api.get<ClarificationItem[]>(`/projects/${projectId}/requirements/clarifications`),
    enabled: !!projectId,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['requirements', projectId] })
    queryClient.invalidateQueries({ queryKey: ['clarifications', projectId] })
  }

  const extractAllMutation = useMutation({
    mutationFn: () => api.post(`/projects/${projectId}/requirements/extract`),
    onSuccess: invalidate,
    onError: (err: Error) => setExtractError(err.message),
  })

  const extractDocMutation = useMutation({
    mutationFn: (documentId: string) => api.post(`/projects/${projectId}/requirements/extract/${documentId}`),
    onSuccess: invalidate,
    onError: (err: Error) => setExtractError(err.message),
  })

  const resolveMutation = useMutation({
    mutationFn: ({ id, note }: { id: string; note: string }) =>
      api.post(`/projects/${projectId}/requirements/clarifications/${id}/resolve`, { resolution_note: note || null }),
    onSuccess: () => {
      invalidate()
      setResolvingId(null)
      setResolutionNote('')
    },
  })

  const completedDocs = (documents ?? []).filter((d) => d.status === 'completed')

  if (!projectsLoading && projects.length === 0) {
    return (
      <div>
        <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">Requirement Analysis</h1>
        <Card>
          <CardContent className="py-10 text-center text-sm text-[var(--color-text-muted)]">
            Create a project first on the{' '}
            <Link to="/projects" className="text-[var(--color-accent)] underline">
              Projects
            </Link>{' '}
            page.
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-[var(--color-text)]">Requirement Analysis</h1>
        <Button
          onClick={() => {
            setExtractError(null)
            extractAllMutation.mutate()
          }}
          disabled={!projectId || completedDocs.length === 0 || extractAllMutation.isPending}
        >
          <Sparkles className="h-4 w-4" />
          {extractAllMutation.isPending ? 'Extracting...' : 'Extract All Documents'}
        </Button>
      </div>

      {!projectId && !projectsLoading && (
        <p className="text-sm text-[var(--color-text-muted)]">Select a project in the top bar.</p>
      )}

      {extractError && (
        <Card className="mb-3 border-[var(--color-danger)]/40">
          <CardContent className="text-sm text-[var(--color-danger)]">{extractError}</CardContent>
        </Card>
      )}

      {projectId && completedDocs.length > 0 && (
        <Card className="mb-4">
          <CardContent>
            <div className="mb-2 text-xs font-medium text-[var(--color-text-muted)]">
              Extract from a single document
            </div>
            <div className="flex flex-wrap gap-2">
              {completedDocs.map((doc) => (
                <Button
                  key={doc.id}
                  variant="secondary"
                  size="sm"
                  disabled={extractDocMutation.isPending}
                  onClick={() => {
                    setExtractError(null)
                    extractDocMutation.mutate(doc.id)
                  }}
                >
                  {doc.filename}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {projectId && completedDocs.length === 0 && !isLoading && (
        <Card className="mb-4">
          <CardContent className="py-6 text-center text-sm text-[var(--color-text-muted)]">
            Upload and process a document on the{' '}
            <Link to="/documents" className="text-[var(--color-accent)] underline">
              Documents
            </Link>{' '}
            page before extracting requirements.
          </CardContent>
        </Card>
      )}

      {isLoading && <p className="text-sm text-[var(--color-text-muted)]">Loading requirements...</p>}

      {requirements && requirements.length > 0 && (
        <Card className="mb-4">
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-[var(--color-border)] text-xs text-[var(--color-text-muted)]">
                <tr>
                  <th className="px-3 py-2 font-medium">ID</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium">State</th>
                  <th className="px-3 py-2 font-medium">Text</th>
                  <th className="px-3 py-2 font-medium">Source</th>
                </tr>
              </thead>
              <tbody>
                {requirements.map((req) => (
                  <tr key={req.id} className="border-b border-[var(--color-border)] last:border-0 align-top">
                    <td className="px-3 py-2 text-[var(--color-text)]">{req.id}</td>
                    <td className="px-3 py-2 text-[var(--color-text-muted)]">{req.requirement_type}</td>
                    <td className="px-3 py-2">
                      <Badge tone={STATE_TONE[req.classification_state]}>{req.classification_state}</Badge>
                    </td>
                    <td className="px-3 py-2 text-[var(--color-text)]">
                      {req.text}
                      {req.rationale && (
                        <div className="mt-1 text-xs text-[var(--color-text-muted)]">{req.rationale}</div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-xs text-[var(--color-text-muted)]">
                      {req.source.document_name}
                      {req.source.page != null && `, p.${req.source.page}`}
                      {req.source.section && `, ${req.source.section}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {requirements && requirements.length === 0 && !isLoading && projectId && (
        <Card className="mb-4">
          <CardContent className="py-10 text-center text-sm text-[var(--color-text-muted)]">
            No requirements extracted yet.
          </CardContent>
        </Card>
      )}

      {clarifications && clarifications.length > 0 && (
        <Card>
          <CardContent>
            <div className="mb-3 text-sm font-semibold text-[var(--color-text)]">Clarification Register</div>
            <div className="space-y-2">
              {clarifications.map((item) => (
                <div key={item.id} className="rounded-md border border-[var(--color-border)] p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-[var(--color-text)]">{item.requirement_id}</span>
                    <Badge tone={item.status === 'open' ? 'warning' : 'success'}>{item.status}</Badge>
                  </div>
                  <p className="mt-1 text-[var(--color-text-muted)]">{item.question}</p>
                  {item.status === 'resolved' && item.resolution_note && (
                    <p className="mt-1 text-xs text-[var(--color-text-muted)]">Resolved: {item.resolution_note}</p>
                  )}
                  {item.status === 'open' && (
                    <div className="mt-2">
                      {resolvingId === item.id ? (
                        <div className="flex gap-2">
                          <input
                            className="h-8 flex-1 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-xs text-[var(--color-text)]"
                            placeholder="Resolution note (optional)"
                            value={resolutionNote}
                            onChange={(e) => setResolutionNote(e.target.value)}
                          />
                          <Button
                            size="sm"
                            onClick={() => resolveMutation.mutate({ id: item.id, note: resolutionNote })}
                            disabled={resolveMutation.isPending}
                          >
                            Confirm
                          </Button>
                          <Button variant="secondary" size="sm" onClick={() => setResolvingId(null)}>
                            Cancel
                          </Button>
                        </div>
                      ) : (
                        <Button variant="secondary" size="sm" onClick={() => setResolvingId(item.id)}>
                          Resolve
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
