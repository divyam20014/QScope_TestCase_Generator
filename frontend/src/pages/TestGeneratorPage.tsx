import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useActiveProject } from '@/lib/active-project'
import { api } from '@/lib/api'
import type { Requirement } from '@/types/requirement'
import type { GenerationJob, JobStatus, TestCategory, TestType } from '@/types/testcase'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, RotateCcw, Sparkles, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

const TEST_TYPES: TestType[] = ['business', 'application', 'system', 'integration', 'e2e', 'security']
const TEST_CATEGORIES: TestCategory[] = ['positive', 'negative', 'edge', 'boundary', 'destructive']

const JOB_STATUS_TONE: Record<JobStatus, 'success' | 'warning' | 'danger' | 'neutral'> = {
  queued: 'neutral',
  running: 'warning',
  paused: 'warning',
  completed: 'success',
  failed: 'danger',
  cancelled: 'neutral',
}

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

export function TestGeneratorPage() {
  const { projectId, projects, isLoading: projectsLoading } = useActiveProject()
  const queryClient = useQueryClient()

  const [selectedRequirementIds, setSelectedRequirementIds] = useState<string[] | null>(null)
  const [selectedTypes, setSelectedTypes] = useState<TestType[]>(['system'])
  const [selectedCategories, setSelectedCategories] = useState<TestCategory[]>(['positive', 'negative'])
  const [jobError, setJobError] = useState<string | null>(null)

  const { data: requirements } = useQuery({
    queryKey: ['requirements', projectId],
    queryFn: () => api.get<Requirement[]>(`/projects/${projectId}/requirements`),
    enabled: !!projectId,
  })

  const { data: jobs } = useQuery({
    queryKey: ['generation-jobs', projectId],
    queryFn: () => api.get<GenerationJob[]>(`/projects/${projectId}/generation/jobs`),
    enabled: !!projectId,
    refetchInterval: 4000,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['generation-jobs', projectId] })
    queryClient.invalidateQueries({ queryKey: ['test-cases', projectId] })
  }

  const createJobMutation = useMutation({
    mutationFn: () =>
      api.post<GenerationJob>(`/projects/${projectId}/generation/jobs`, {
        requirement_ids: selectedRequirementIds,
        test_types: selectedTypes,
        test_categories: selectedCategories,
      }),
    onSuccess: invalidate,
    onError: (err: Error) => setJobError(err.message),
  })

  const resumeMutation = useMutation({
    mutationFn: (jobId: string) => api.post(`/projects/${projectId}/generation/jobs/${jobId}/resume`),
    onSuccess: invalidate,
  })

  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => api.post(`/projects/${projectId}/generation/jobs/${jobId}/cancel`),
    onSuccess: invalidate,
  })

  const sortedJobs = [...(jobs ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at))

  if (!projectsLoading && projects.length === 0) {
    return (
      <div>
        <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">Test Case Generator</h1>
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
      <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">Test Case Generator</h1>

      {!projectId && !projectsLoading && (
        <p className="text-sm text-[var(--color-text-muted)]">Select a project in the top bar.</p>
      )}

      {projectId && (
        <Card className="mb-4">
          <CardHeader>
            <CardTitle>New generation job</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="mb-1 text-xs font-medium text-[var(--color-text-muted)]">
                Requirements ({selectedRequirementIds === null ? 'all' : selectedRequirementIds.length} selected)
              </div>
              <div className="max-h-40 overflow-y-auto rounded-md border border-[var(--color-border)] p-2">
                <label className="flex items-center gap-2 border-b border-[var(--color-border)] pb-1 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedRequirementIds === null}
                    onChange={() => setSelectedRequirementIds((prev) => (prev === null ? [] : null))}
                  />
                  All requirements
                </label>
                {(requirements ?? []).map((req) => (
                  <label key={req.id} className="flex items-center gap-2 py-1 text-sm">
                    <input
                      type="checkbox"
                      disabled={selectedRequirementIds === null}
                      checked={selectedRequirementIds !== null && selectedRequirementIds.includes(req.id)}
                      onChange={() =>
                        setSelectedRequirementIds((prev) => (prev === null ? [req.id] : toggle(prev, req.id)))
                      }
                    />
                    <span className="text-[var(--color-text)]">{req.id}</span>
                    <span className="truncate text-[var(--color-text-muted)]">{req.text}</span>
                  </label>
                ))}
                {(requirements ?? []).length === 0 && (
                  <p className="py-2 text-xs text-[var(--color-text-muted)]">
                    No requirements yet - extract some on the{' '}
                    <Link to="/requirement-analysis" className="text-[var(--color-accent)] underline">
                      Requirement Analysis
                    </Link>{' '}
                    page first.
                  </p>
                )}
              </div>
            </div>

            <div>
              <div className="mb-1 text-xs font-medium text-[var(--color-text-muted)]">Test types</div>
              <div className="flex flex-wrap gap-2">
                {TEST_TYPES.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setSelectedTypes((prev) => toggle(prev, t))}
                    className={`rounded-full border px-3 py-1 text-xs ${
                      selectedTypes.includes(t)
                        ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]'
                        : 'border-[var(--color-border)] text-[var(--color-text-muted)]'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="mb-1 text-xs font-medium text-[var(--color-text-muted)]">Categories</div>
              <div className="flex flex-wrap gap-2">
                {TEST_CATEGORIES.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setSelectedCategories((prev) => toggle(prev, c))}
                    className={`rounded-full border px-3 py-1 text-xs ${
                      selectedCategories.includes(c)
                        ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]'
                        : 'border-[var(--color-border)] text-[var(--color-text-muted)]'
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>

            {jobError && <p className="text-sm text-[var(--color-danger)]">{jobError}</p>}

            <Button
              onClick={() => {
                setJobError(null)
                createJobMutation.mutate()
              }}
              disabled={
                selectedTypes.length === 0 || selectedCategories.length === 0 || createJobMutation.isPending
              }
            >
              <Sparkles className="h-4 w-4" />
              {createJobMutation.isPending ? 'Generating...' : 'Generate Test Cases'}
            </Button>
            <p className="text-xs text-[var(--color-text-muted)]">
              This runs synchronously and may take a while for many requirement/type/category combinations.
            </p>
          </CardContent>
        </Card>
      )}

      {projectId && sortedJobs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Generation jobs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {sortedJobs.map((job) => {
              const completedBatches = Object.values(job.results).filter((r) => r.status === 'completed').length
              return (
                <div key={job.id} className="rounded-md border border-[var(--color-border)] p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge tone={JOB_STATUS_TONE[job.status]}>{job.status}</Badge>
                      <span className="text-xs text-[var(--color-text-muted)]">
                        {completedBatches}/{job.batches.length} batches - {new Date(job.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="flex gap-1">
                      {(job.status === 'paused' || job.status === 'failed') && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => resumeMutation.mutate(job.id)}
                          disabled={resumeMutation.isPending}
                        >
                          <Play className="h-3.5 w-3.5" />
                          Resume
                        </Button>
                      )}
                      {job.status !== 'completed' && job.status !== 'cancelled' && (
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => cancelMutation.mutate(job.id)}
                          disabled={cancelMutation.isPending}
                        >
                          <XCircle className="h-3.5 w-3.5" />
                          Cancel
                        </Button>
                      )}
                    </div>
                  </div>
                  <div className="mt-1 text-xs text-[var(--color-text-muted)]">
                    {job.test_types.join(', ')} x {job.test_categories.join(', ')} across {job.requirement_ids.length}{' '}
                    requirement(s)
                  </div>
                  {job.error && <div className="mt-1 text-xs text-[var(--color-danger)]">{job.error}</div>}
                  {job.status === 'paused' && job.retry_after_seconds != null && (
                    <div className="mt-1 flex items-center gap-1 text-xs text-[var(--color-warning)]">
                      <RotateCcw className="h-3 w-3" />
                      Quota paused - retry after {Math.ceil(job.retry_after_seconds)}s, then click Resume.
                    </div>
                  )}
                </div>
              )
            })}
          </CardContent>
        </Card>
      )}

      {projectId && (
        <p className="mt-4 text-xs text-[var(--color-text-muted)]">
          Generated test cases appear in the{' '}
          <Link to="/test-repository" className="text-[var(--color-accent)] underline">
            Test Case Repository
          </Link>
          .
        </p>
      )}
    </div>
  )
}
