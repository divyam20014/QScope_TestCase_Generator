import { TestCaseFormDialog } from '@/components/repository/TestCaseFormDialog'
import { TestCaseHistoryDialog } from '@/components/repository/TestCaseHistoryDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useActiveProject } from '@/lib/active-project'
import { api } from '@/lib/api'
import type { Requirement } from '@/types/requirement'
import type { ManualTestCaseCreate, Priority, TestCase, TestCaseUpdate, TestCategory, TestType } from '@/types/testcase'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, ArrowUpDown, Copy, History, Lock, Pencil, Plus, Trash2, Unlock } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

const PRIORITY_TONE: Record<Priority, 'danger' | 'warning' | 'neutral'> = {
  critical: 'danger',
  high: 'warning',
  medium: 'neutral',
  low: 'neutral',
}

const COVERAGE_TONE: Record<string, 'success' | 'warning' | 'neutral'> = {
  covered: 'success',
  partial: 'warning',
  not_covered: 'neutral',
  not_assessed: 'neutral',
}

type SortKey = 'id' | 'requirement_id' | 'title' | 'test_type' | 'test_category' | 'priority'
const PAGE_SIZE = 20

export function RepositoryPage() {
  const { projectId, projects, isLoading: projectsLoading } = useActiveProject()
  const queryClient = useQueryClient()

  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<TestType | ''>('')
  const [categoryFilter, setCategoryFilter] = useState<TestCategory | ''>('')
  const [sortKey, setSortKey] = useState<SortKey>('id')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState<TestCase | null>(null)
  const [adding, setAdding] = useState(false)
  const [historyFor, setHistoryFor] = useState<string | null>(null)

  const { data: testCases, isLoading } = useQuery({
    queryKey: ['test-cases', projectId],
    queryFn: () => api.get<TestCase[]>(`/projects/${projectId}/test-cases`),
    enabled: !!projectId,
  })

  const { data: requirements } = useQuery({
    queryKey: ['requirements', projectId],
    queryFn: () => api.get<Requirement[]>(`/projects/${projectId}/requirements`),
    enabled: !!projectId,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['test-cases', projectId] })

  const createMutation = useMutation({
    mutationFn: (data: ManualTestCaseCreate) => api.post<TestCase>(`/projects/${projectId}/test-cases`, data),
    onSuccess: () => {
      invalidate()
      setAdding(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: TestCaseUpdate }) =>
      api.patch<TestCase>(`/projects/${projectId}/test-cases/${id}`, data),
    onSuccess: () => {
      invalidate()
      setEditing(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/projects/${projectId}/test-cases/${id}`),
    onSuccess: invalidate,
  })

  const copyMutation = useMutation({
    mutationFn: (id: string) => api.post<TestCase>(`/projects/${projectId}/test-cases/${id}/copy`),
    onSuccess: invalidate,
  })

  const lockMutation = useMutation({
    mutationFn: ({ id, locked }: { id: string; locked: boolean }) =>
      api.post<TestCase>(`/projects/${projectId}/test-cases/${id}/lock?locked=${locked}`),
    onSuccess: invalidate,
  })

  const bulkMutation = useMutation({
    mutationFn: ({ ids, action }: { ids: string[]; action: string }) =>
      api.post<{ changed: number; skipped_locked: string[] }>(`/projects/${projectId}/test-cases/bulk`, {
        ids,
        action,
      }),
    onSuccess: () => {
      invalidate()
      setSelected(new Set())
    },
  })

  const filteredSorted = useMemo(() => {
    if (!testCases) return []
    const term = search.trim().toLowerCase()
    const filtered = testCases.filter((tc) => {
      if (typeFilter && tc.test_type !== typeFilter) return false
      if (categoryFilter && tc.test_category !== categoryFilter) return false
      if (term) {
        const haystack = `${tc.id} ${tc.requirement_id} ${tc.title} ${tc.scenario_description}`.toLowerCase()
        if (!haystack.includes(term)) return false
      }
      return true
    })
    const sorted = [...filtered].sort((a, b) => {
      const result = String(a[sortKey]).localeCompare(String(b[sortKey]))
      return sortDir === 'asc' ? result : -result
    })
    return sorted
  }, [testCases, typeFilter, categoryFilter, search, sortKey, sortDir])

  const pageCount = Math.max(1, Math.ceil(filteredSorted.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount - 1)
  const pageRows = filteredSorted.slice(currentPage * PAGE_SIZE, currentPage * PAGE_SIZE + PAGE_SIZE)

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
    setPage(0)
  }

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleSelectAllOnPage() {
    const pageIds = pageRows.map((t) => t.id)
    const allSelected = pageIds.every((id) => selected.has(id))
    setSelected((prev) => {
      const next = new Set(prev)
      pageIds.forEach((id) => (allSelected ? next.delete(id) : next.add(id)))
      return next
    })
  }

  function sortIcon(key: SortKey) {
    if (sortKey !== key) return <ArrowUpDown className="h-3 w-3 opacity-40" />
    return sortDir === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
  }

  const selectedIds = Array.from(selected)

  if (!projectsLoading && projects.length === 0) {
    return (
      <div>
        <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">Test Case Repository</h1>
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
        <h1 className="text-xl font-semibold text-[var(--color-text)]">Test Case Repository</h1>
        <Button onClick={() => setAdding(true)} disabled={!projectId || !requirements?.length}>
          <Plus className="h-4 w-4" />
          Add Test Case
        </Button>
      </div>

      {!projectId && !projectsLoading && (
        <p className="text-sm text-[var(--color-text-muted)]">Select a project in the top bar.</p>
      )}

      {projectId && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Input
              placeholder="Search by id, requirement, or title..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(0)
              }}
              className="max-w-xs"
            />
            <select
              className="h-10 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-sm text-[var(--color-text)]"
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value as TestType | '')
                setPage(0)
              }}
            >
              <option value="">All types</option>
              {(['business', 'application', 'system', 'integration', 'e2e', 'security'] as TestType[]).map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <select
              className="h-10 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-sm text-[var(--color-text)]"
              value={categoryFilter}
              onChange={(e) => {
                setCategoryFilter(e.target.value as TestCategory | '')
                setPage(0)
              }}
            >
              <option value="">All categories</option>
              {(['positive', 'negative', 'edge', 'boundary', 'destructive'] as TestCategory[]).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>

            {selectedIds.length > 0 && (
              <div className="ml-auto flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
                {selectedIds.length} selected
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => bulkMutation.mutate({ ids: selectedIds, action: 'approve' })}
                >
                  Approve
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => bulkMutation.mutate({ ids: selectedIds, action: 'lock' })}
                >
                  Lock
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => {
                    if (confirm(`Delete ${selectedIds.length} test case(s)? Locked ones will be skipped.`)) {
                      bulkMutation.mutate({ ids: selectedIds, action: 'delete' })
                    }
                  }}
                >
                  Delete
                </Button>
              </div>
            )}
          </div>

          {isLoading && <p className="text-sm text-[var(--color-text-muted)]">Loading test cases...</p>}

          {testCases && testCases.length === 0 && (
            <Card>
              <CardContent className="py-10 text-center text-sm text-[var(--color-text-muted)]">
                No test cases yet. Generate some from the Test Case Generator, or add one manually.
              </CardContent>
            </Card>
          )}

          {testCases && testCases.length > 0 && (
            <Card>
              <CardContent className="overflow-x-auto p-0">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-[var(--color-border)] text-xs text-[var(--color-text-muted)]">
                    <tr>
                      <th className="px-3 py-2 font-medium">
                        <input
                          type="checkbox"
                          checked={pageRows.length > 0 && pageRows.every((t) => selected.has(t.id))}
                          onChange={toggleSelectAllOnPage}
                        />
                      </th>
                      {(
                        [
                          ['id', 'Test Case ID'],
                          ['requirement_id', 'Requirement'],
                          ['title', 'Test Case'],
                          ['test_type', 'Type'],
                          ['test_category', 'Category'],
                          ['priority', 'Priority'],
                        ] as [SortKey, string][]
                      ).map(([key, label]) => (
                        <th key={key} className="px-3 py-2 font-medium">
                          <button type="button" className="flex items-center gap-1" onClick={() => toggleSort(key)}>
                            {label}
                            {sortIcon(key)}
                          </button>
                        </th>
                      ))}
                      <th className="px-3 py-2 font-medium">Coverage</th>
                      <th className="px-3 py-2 font-medium">Flags</th>
                      <th className="px-3 py-2 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageRows.map((tc) => (
                      <tr key={tc.id} className="border-b border-[var(--color-border)] last:border-0">
                        <td className="px-3 py-2">
                          <input type="checkbox" checked={selected.has(tc.id)} onChange={() => toggleSelected(tc.id)} />
                        </td>
                        <td className="px-3 py-2 text-[var(--color-text)]">{tc.id}</td>
                        <td className="px-3 py-2 text-[var(--color-text-muted)]">{tc.requirement_id}</td>
                        <td className="px-3 py-2 text-[var(--color-text)]">{tc.title}</td>
                        <td className="px-3 py-2 text-[var(--color-text-muted)]">{tc.test_type}</td>
                        <td className="px-3 py-2 text-[var(--color-text-muted)]">{tc.test_category}</td>
                        <td className="px-3 py-2">
                          <Badge tone={PRIORITY_TONE[tc.priority]}>{tc.priority}</Badge>
                        </td>
                        <td className="px-3 py-2">
                          <Badge tone={COVERAGE_TONE[tc.coverage_status] ?? 'neutral'}>
                            {tc.coverage_status.replace('_', ' ')}
                          </Badge>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex flex-wrap gap-1">
                            {tc.destructive && <Badge tone="danger">destructive</Badge>}
                            {tc.approved && <Badge tone="success">approved</Badge>}
                            {tc.locked && <Badge tone="warning">locked</Badge>}
                            {tc.manually_edited && <Badge tone="neutral">edited</Badge>}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex justify-end gap-1">
                            <Button variant="ghost" size="sm" title="Edit" onClick={() => setEditing(tc)}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button variant="ghost" size="sm" title="Copy" onClick={() => copyMutation.mutate(tc.id)}>
                              <Copy className="h-3.5 w-3.5" />
                            </Button>
                            <Button variant="ghost" size="sm" title="History" onClick={() => setHistoryFor(tc.id)}>
                              <History className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              title={tc.locked ? 'Unlock' : 'Lock'}
                              onClick={() => lockMutation.mutate({ id: tc.id, locked: !tc.locked })}
                            >
                              {tc.locked ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
                            </Button>
                            <Button
                              variant="danger"
                              size="sm"
                              title="Delete"
                              disabled={tc.locked}
                              onClick={() => {
                                if (confirm(`Delete ${tc.id}?`)) deleteMutation.mutate(tc.id)
                              }}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
              <div className="flex items-center justify-between border-t border-[var(--color-border)] px-3 py-2 text-xs text-[var(--color-text-muted)]">
                <span>
                  {filteredSorted.length} test case{filteredSorted.length === 1 ? '' : 's'} - page {currentPage + 1} of{' '}
                  {pageCount}
                </span>
                <div className="flex gap-1">
                  <Button variant="secondary" size="sm" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={currentPage === 0}>
                    Prev
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                    disabled={currentPage >= pageCount - 1}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </Card>
          )}
        </>
      )}

      {adding && projectId && (
        <TestCaseFormDialog
          open={adding}
          onClose={() => setAdding(false)}
          requirements={requirements ?? []}
          isSaving={createMutation.isPending}
          onCreate={(data) => createMutation.mutate(data)}
          onUpdate={() => {}}
        />
      )}

      {editing && (
        <TestCaseFormDialog
          open={!!editing}
          onClose={() => setEditing(null)}
          requirements={requirements ?? []}
          testCase={editing}
          isSaving={updateMutation.isPending}
          onCreate={() => {}}
          onUpdate={(data) => updateMutation.mutate({ id: editing.id, data })}
        />
      )}

      {historyFor && projectId && (
        <TestCaseHistoryDialog projectId={projectId} testCaseId={historyFor} onClose={() => setHistoryFor(null)} />
      )}
    </div>
  )
}
