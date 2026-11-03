import { Dialog } from '@/components/ui/dialog'
import { api } from '@/lib/api'
import type { DocumentRecord, ExtractionResult } from '@/types/document'
import { useQuery } from '@tanstack/react-query'

export function DocumentPreviewDialog({
  projectId,
  document: doc,
  onClose,
}: {
  projectId: string
  document: DocumentRecord
  onClose: () => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['document-preview', projectId, doc.id],
    queryFn: () => api.get<ExtractionResult>(`/projects/${projectId}/documents/${doc.id}/preview`),
  })

  return (
    <Dialog open onClose={onClose} title={`Preview: ${doc.filename}`}>
      <div className="max-h-[60vh] max-w-full overflow-y-auto">
        {isLoading && <p className="text-sm text-[var(--color-text-muted)]">Loading...</p>}

        {data && data.warnings.length > 0 && (
          <div className="mb-3 rounded-md bg-[var(--color-warning)]/10 p-3 text-xs text-[var(--color-warning)]">
            {data.warnings.map((w, i) => (
              <div key={i}>
                {w.message}
                {w.page != null && ` (page ${w.page})`}
                {w.sheet != null && ` (sheet '${w.sheet}')`}
              </div>
            ))}
          </div>
        )}

        {data && data.blocks.length === 0 && (
          <p className="text-sm text-[var(--color-text-muted)]">No extractable content.</p>
        )}

        {data?.blocks.map((block) => {
          const location = [
            block.page != null ? `p.${block.page}` : null,
            block.sheet ? `sheet: ${block.sheet}` : null,
          ]
            .filter(Boolean)
            .join(' · ')

          if (block.type === 'heading') {
            return (
              <h4
                key={block.block_id}
                className="mt-3 text-sm font-semibold text-[var(--color-text)]"
                title={location}
              >
                {block.text}
              </h4>
            )
          }
          if (block.type === 'table' && block.table_data) {
            return (
              <div key={block.block_id} className="my-2 overflow-x-auto" title={location}>
                <table className="w-full border-collapse text-xs">
                  <tbody>
                    {block.table_data.map((row, rIdx) => (
                      <tr key={rIdx}>
                        {row.map((cell, cIdx) => (
                          <td
                            key={cIdx}
                            className="border border-[var(--color-border)] px-2 py-1 text-[var(--color-text)]"
                          >
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
          return (
            <p
              key={block.block_id}
              className="mt-1 text-sm text-[var(--color-text-muted)]"
              title={location}
            >
              {block.type === 'list_item' ? `• ${block.text}` : block.text}
            </p>
          )
        })}
      </div>
    </Dialog>
  )
}
