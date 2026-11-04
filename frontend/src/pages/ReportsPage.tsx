import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useActiveProject } from '@/lib/active-project'
import { api } from '@/lib/api'
import type { ExportFormat, ExportRecord } from '@/types/export'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

const FORMATS: { id: ExportFormat; label: string }[] = [
  { id: 'xlsx', label: 'Excel (.xlsx)' },
  { id: 'docx', label: 'Word (.docx)' },
  { id: 'pdf', label: 'PDF' },
  { id: 'csv', label: 'CSV' },
  { id: 'json', label: 'JSON' },
]

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function triggerDownload(projectId: string, record: ExportRecord) {
  const blob = await api.downloadBlob(`/projects/${projectId}/exports/${record.id}/download`)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = record.filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function ReportsPage() {
  const { projectId, projects, isLoading: projectsLoading } = useActiveProject()
  const queryClient = useQueryClient()
  const [exportError, setExportError] = useState<string | null>(null)

  const { data: exports, isLoading } = useQuery({
    queryKey: ['exports', projectId],
    queryFn: () => api.get<ExportRecord[]>(`/projects/${projectId}/exports`),
    enabled: !!projectId,
  })

  const createMutation = useMutation({
    mutationFn: (format: ExportFormat) =>
      api.post<ExportRecord>(`/projects/${projectId}/exports`, { format, scope: {} }),
    onSuccess: (record) => {
      queryClient.invalidateQueries({ queryKey: ['exports', projectId] })
      if (projectId) void triggerDownload(projectId, record)
    },
    onError: (err: Error) => setExportError(err.message),
  })

  if (!projectsLoading && projects.length === 0) {
    return (
      <div>
        <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">Reports</h1>
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
      <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">Reports</h1>

      {!projectId && !projectsLoading && (
        <p className="text-sm text-[var(--color-text-muted)]">Select a project in the top bar.</p>
      )}

      {projectId && (
        <>
          <Card className="mb-4">
            <CardHeader>
              <CardTitle>Export the whole project</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="mb-3 text-xs text-[var(--color-text-muted)]">
                Includes every test case, the traceability matrix, and the clarification register (CSV is test
                cases only - it has no room for extra sheets/sections).
              </p>
              <div className="flex flex-wrap gap-2">
                {FORMATS.map((f) => (
                  <Button
                    key={f.id}
                    variant="secondary"
                    onClick={() => {
                      setExportError(null)
                      createMutation.mutate(f.id)
                    }}
                    disabled={createMutation.isPending}
                  >
                    <Download className="h-4 w-4" />
                    {f.label}
                  </Button>
                ))}
              </div>
              {exportError && <p className="mt-2 text-sm text-[var(--color-danger)]">{exportError}</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Export history</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto p-0">
              {isLoading && <p className="p-4 text-sm text-[var(--color-text-muted)]">Loading...</p>}
              {exports && exports.length === 0 && (
                <p className="p-6 text-center text-sm text-[var(--color-text-muted)]">No exports yet.</p>
              )}
              {exports && exports.length > 0 && (
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-[var(--color-border)] text-xs text-[var(--color-text-muted)]">
                    <tr>
                      <th className="px-3 py-2 font-medium">Format</th>
                      <th className="px-3 py-2 font-medium">Test Cases</th>
                      <th className="px-3 py-2 font-medium">Size</th>
                      <th className="px-3 py-2 font-medium">Created</th>
                      <th className="px-3 py-2 font-medium text-right">Download</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...exports]
                      .sort((a, b) => b.created_at.localeCompare(a.created_at))
                      .map((record) => (
                        <tr key={record.id} className="border-b border-[var(--color-border)] last:border-0">
                          <td className="px-3 py-2">
                            <Badge tone="neutral">{record.format}</Badge>
                          </td>
                          <td className="px-3 py-2 text-[var(--color-text-muted)]">{record.test_case_count}</td>
                          <td className="px-3 py-2 text-[var(--color-text-muted)]">{formatSize(record.size_bytes)}</td>
                          <td className="px-3 py-2 text-[var(--color-text-muted)]">
                            {new Date(record.created_at).toLocaleString()}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <Button variant="ghost" size="sm" onClick={() => triggerDownload(projectId, record)}>
                              <Download className="h-3.5 w-3.5" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
