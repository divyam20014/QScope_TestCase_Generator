import { Dialog } from '@/components/ui/dialog'
import { api } from '@/lib/api'
import type { TestCaseVersionEntry } from '@/types/testcase'
import { useQuery } from '@tanstack/react-query'

interface TestCaseHistoryDialogProps {
  projectId: string
  testCaseId: string
  onClose: () => void
}

export function TestCaseHistoryDialog({ projectId, testCaseId, onClose }: TestCaseHistoryDialogProps) {
  const { data: history, isLoading } = useQuery({
    queryKey: ['test-case-history', projectId, testCaseId],
    queryFn: () => api.get<TestCaseVersionEntry[]>(`/projects/${projectId}/test-cases/${testCaseId}/history`),
  })

  return (
    <Dialog open onClose={onClose} title={`History - ${testCaseId}`}>
      {isLoading && <p className="text-sm text-[var(--color-text-muted)]">Loading history...</p>}
      {history && history.length === 0 && (
        <p className="text-sm text-[var(--color-text-muted)]">No prior versions - this test case has not been edited.</p>
      )}
      {history && history.length > 0 && (
        <div className="max-h-[60vh] space-y-3 overflow-y-auto">
          {[...history].reverse().map((entry) => (
            <div key={entry.id} className="rounded-md border border-[var(--color-border)] p-3 text-sm">
              <div className="mb-1 text-xs text-[var(--color-text-muted)]">
                Snapshot before edit at {new Date(entry.created_at).toLocaleString()}
              </div>
              <div className="font-medium text-[var(--color-text)]">{entry.snapshot.title}</div>
              <div className="mt-1 text-[var(--color-text-muted)]">{entry.snapshot.expected_result}</div>
            </div>
          ))}
        </div>
      )}
    </Dialog>
  )
}
