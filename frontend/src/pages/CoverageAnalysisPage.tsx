import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useActiveProject } from '@/lib/active-project'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { CoverageStatus, DuplicateGroup, ProjectCoverage, QualityIssue, TraceabilityRow } from '@/types/coverage'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

const COVERAGE_TONE: Record<CoverageStatus, 'success' | 'warning' | 'neutral'> = {
  covered: 'success',
  partial: 'warning',
  not_covered: 'neutral',
}

type Tab = 'coverage' | 'traceability' | 'duplicates' | 'quality'

const TABS: { id: Tab; label: string }[] = [
  { id: 'coverage', label: 'Coverage' },
  { id: 'traceability', label: 'Traceability Matrix' },
  { id: 'duplicates', label: 'Duplicates' },
  { id: 'quality', label: 'Quality Review' },
]

export function CoverageAnalysisPage() {
  const { projectId, projects, isLoading: projectsLoading } = useActiveProject()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<Tab>('coverage')
  const [reviewError, setReviewError] = useState<string | null>(null)

  const { data: coverage, isLoading: coverageLoading } = useQuery({
    queryKey: ['coverage', projectId],
    queryFn: () => api.get<ProjectCoverage>(`/projects/${projectId}/coverage`),
    enabled: !!projectId && tab === 'coverage',
  })

  const { data: traceability } = useQuery({
    queryKey: ['traceability', projectId],
    queryFn: () => api.get<TraceabilityRow[]>(`/projects/${projectId}/coverage/traceability`),
    enabled: !!projectId && tab === 'traceability',
  })

  const { data: duplicates } = useQuery({
    queryKey: ['duplicates', projectId],
    queryFn: () => api.get<DuplicateGroup[]>(`/projects/${projectId}/coverage/duplicates`),
    enabled: !!projectId && tab === 'duplicates',
  })

  const { data: qualityIssues } = useQuery({
    queryKey: ['quality-issues', projectId],
    queryFn: () => api.get<QualityIssue[]>(`/projects/${projectId}/quality-review/issues`),
    enabled: !!projectId && tab === 'quality',
  })

  const runReviewMutation = useMutation({
    mutationFn: () => api.post<{ requirements_reviewed: number; issues_found: number }>(`/projects/${projectId}/quality-review`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['quality-issues', projectId] }),
    onError: (err: Error) => setReviewError(err.message),
  })

  const resolveIssueMutation = useMutation({
    mutationFn: (issueId: string) => api.post(`/projects/${projectId}/quality-review/issues/${issueId}/resolve`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['quality-issues', projectId] }),
  })

  if (!projectsLoading && projects.length === 0) {
    return (
      <div>
        <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">Coverage Analysis</h1>
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
      <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">Coverage Analysis</h1>

      {!projectId && !projectsLoading && (
        <p className="text-sm text-[var(--color-text-muted)]">Select a project in the top bar.</p>
      )}

      {projectId && (
        <>
          <div className="mb-4 flex gap-1 border-b border-[var(--color-border)]">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  'px-3 py-2 text-sm font-medium',
                  tab === t.id
                    ? 'border-b-2 border-[var(--color-accent)] text-[var(--color-accent)]'
                    : 'text-[var(--color-text-muted)]',
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          {tab === 'coverage' && (
            <>
              {coverageLoading && <p className="text-sm text-[var(--color-text-muted)]">Loading...</p>}
              {coverage && (
                <>
                  <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Card>
                      <CardContent className="text-center">
                        <div className="text-2xl font-semibold text-[var(--color-text)]">
                          {coverage.coverage_percentage}%
                        </div>
                        <div className="text-xs text-[var(--color-text-muted)]">Covered</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="text-center">
                        <div className="text-2xl font-semibold text-[var(--color-text)]">{coverage.covered}</div>
                        <div className="text-xs text-[var(--color-text-muted)]">Requirements covered</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="text-center">
                        <div className="text-2xl font-semibold text-[var(--color-text)]">{coverage.partial}</div>
                        <div className="text-xs text-[var(--color-text-muted)]">Partial</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="text-center">
                        <div className="text-2xl font-semibold text-[var(--color-text)]">{coverage.not_covered}</div>
                        <div className="text-xs text-[var(--color-text-muted)]">Not covered</div>
                      </CardContent>
                    </Card>
                  </div>

                  <Card>
                    <CardContent className="overflow-x-auto p-0">
                      <table className="w-full text-left text-sm">
                        <thead className="border-b border-[var(--color-border)] text-xs text-[var(--color-text-muted)]">
                          <tr>
                            <th className="px-3 py-2 font-medium">Requirement</th>
                            <th className="px-3 py-2 font-medium">Status</th>
                            <th className="px-3 py-2 font-medium"># Test Cases</th>
                            <th className="px-3 py-2 font-medium">Categories Covered</th>
                            <th className="px-3 py-2 font-medium">Missing</th>
                          </tr>
                        </thead>
                        <tbody>
                          {coverage.per_requirement.map((row) => (
                            <tr key={row.requirement_id} className="border-b border-[var(--color-border)] last:border-0">
                              <td className="px-3 py-2 text-[var(--color-text)]">{row.requirement_id}</td>
                              <td className="px-3 py-2">
                                <Badge tone={COVERAGE_TONE[row.status]}>{row.status}</Badge>
                              </td>
                              <td className="px-3 py-2 text-[var(--color-text-muted)]">{row.test_case_count}</td>
                              <td className="px-3 py-2 text-[var(--color-text-muted)]">
                                {row.categories_covered.join(', ') || '-'}
                              </td>
                              <td className="px-3 py-2 text-[var(--color-text-muted)]">
                                {row.missing_categories.join(', ') || '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </CardContent>
                  </Card>
                </>
              )}
            </>
          )}

          {tab === 'traceability' && (
            <Card>
              <CardContent className="overflow-x-auto p-0">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-[var(--color-border)] text-xs text-[var(--color-text-muted)]">
                    <tr>
                      <th className="px-3 py-2 font-medium">Requirement</th>
                      <th className="px-3 py-2 font-medium">Text</th>
                      <th className="px-3 py-2 font-medium">Classification</th>
                      <th className="px-3 py-2 font-medium">Coverage</th>
                      <th className="px-3 py-2 font-medium">Test Cases</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(traceability ?? []).map((row) => (
                      <tr key={row.requirement_id} className="border-b border-[var(--color-border)] last:border-0 align-top">
                        <td className="px-3 py-2 text-[var(--color-text)]">{row.requirement_id}</td>
                        <td className="px-3 py-2 text-[var(--color-text-muted)]">{row.requirement_text}</td>
                        <td className="px-3 py-2 text-[var(--color-text-muted)]">{row.classification_state}</td>
                        <td className="px-3 py-2">
                          <Badge tone={COVERAGE_TONE[row.coverage_status as CoverageStatus] ?? 'neutral'}>
                            {row.coverage_status}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 text-xs text-[var(--color-text-muted)]">
                          {row.test_case_ids.join(', ') || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(traceability ?? []).length === 0 && (
                  <p className="py-10 text-center text-sm text-[var(--color-text-muted)]">No requirements yet.</p>
                )}
              </CardContent>
            </Card>
          )}

          {tab === 'duplicates' && (
            <Card>
              <CardContent className="space-y-2">
                {(duplicates ?? []).length === 0 && (
                  <p className="py-6 text-center text-sm text-[var(--color-text-muted)]">
                    No duplicate test cases found.
                  </p>
                )}
                {(duplicates ?? []).map((group, i) => (
                  <div key={i} className="rounded-md border border-[var(--color-border)] p-3 text-sm">
                    <div className="flex items-center gap-2">
                      <Badge tone="warning">{group.method}</Badge>
                      {group.similarity != null && (
                        <span className="text-xs text-[var(--color-text-muted)]">
                          similarity &gt;= {group.similarity}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-[var(--color-text)]">{group.test_case_ids.join(', ')}</div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {tab === 'quality' && (
            <Card>
              <CardContent>
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-xs text-[var(--color-text-muted)]">
                    Runs a separate Gemini pass over existing test cases to flag weak expected results,
                    miscategorization, or unclear steps.
                  </p>
                  <Button
                    size="sm"
                    onClick={() => {
                      setReviewError(null)
                      runReviewMutation.mutate()
                    }}
                    disabled={runReviewMutation.isPending}
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    {runReviewMutation.isPending ? 'Reviewing...' : 'Run Quality Review'}
                  </Button>
                </div>
                {reviewError && <p className="mb-2 text-sm text-[var(--color-danger)]">{reviewError}</p>}
                {runReviewMutation.isSuccess && (
                  <p className="mb-2 text-xs text-[var(--color-success)]">
                    Reviewed {runReviewMutation.data.requirements_reviewed} requirement(s), found{' '}
                    {runReviewMutation.data.issues_found} issue(s).
                  </p>
                )}

                <div className="space-y-2">
                  {(qualityIssues ?? []).length === 0 && (
                    <p className="py-6 text-center text-sm text-[var(--color-text-muted)]">No issues recorded.</p>
                  )}
                  {(qualityIssues ?? []).map((issue) => (
                    <div key={issue.id} className="rounded-md border border-[var(--color-border)] p-3 text-sm">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge tone="warning">{issue.issue_type}</Badge>
                          <span className="text-xs text-[var(--color-text-muted)]">
                            {issue.requirement_id} / {issue.test_case_id}
                          </span>
                        </div>
                        <Badge tone={issue.status === 'open' ? 'warning' : 'success'}>{issue.status}</Badge>
                      </div>
                      <p className="mt-1 text-[var(--color-text)]">{issue.explanation}</p>
                      {issue.suggested_fix && (
                        <p className="mt-1 text-xs text-[var(--color-text-muted)]">Suggested fix: {issue.suggested_fix}</p>
                      )}
                      {issue.status === 'open' && (
                        <Button
                          variant="secondary"
                          size="sm"
                          className="mt-2"
                          onClick={() => resolveIssueMutation.mutate(issue.id)}
                          disabled={resolveIssueMutation.isPending}
                        >
                          Mark resolved
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
