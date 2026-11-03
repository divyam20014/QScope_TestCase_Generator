import { DocumentPreviewDialog } from '@/components/documents/DocumentPreviewDialog'
import { RagSearchPanel } from '@/components/documents/RagSearchPanel'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { api } from '@/lib/api'
import { useActiveProject } from '@/lib/active-project'
import type { DocumentRecord } from '@/types/document'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Copy, Download, Eye, ShieldCheck, Trash2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function statusTone(status: DocumentRecord['status']) {
  if (status === 'completed') return 'success' as const
  if (status === 'failed') return 'danger' as const
  return 'neutral' as const
}

export function DocumentsPage() {
  const { projectId, projects, isLoading: projectsLoading } = useActiveProject()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [previewDoc, setPreviewDoc] = useState<DocumentRecord | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const { data: documents, isLoading } = useQuery({
    queryKey: ['documents', projectId],
    queryFn: () => api.get<DocumentRecord[]>(`/projects/${projectId}/documents`),
    enabled: !!projectId,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['documents', projectId] })
    queryClient.invalidateQueries({ queryKey: ['projects'] })
  }

  const uploadMutation = useMutation({
    mutationFn: (files: FileList) => {
      const formData = new FormData()
      Array.from(files).forEach((file) => formData.append('files', file))
      return api.upload<DocumentRecord[]>(`/projects/${projectId}/documents`, formData)
    },
    onSuccess: invalidate,
    onError: (err: Error) => setUploadError(err.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => api.delete(`/projects/${projectId}/documents/${documentId}`),
    onSuccess: invalidate,
  })

  const authoritativeMutation = useMutation({
    mutationFn: ({ documentId, value }: { documentId: string; value: boolean }) =>
      api.post<DocumentRecord>(`/projects/${projectId}/documents/${documentId}/authoritative?value=${value}`),
    onSuccess: invalidate,
  })

  function handleFilesSelected(files: FileList | null) {
    if (!files || files.length === 0) return
    setUploadError(null)
    uploadMutation.mutate(files)
  }

  if (!projectsLoading && projects.length === 0) {
    return (
      <div>
        <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">Documents</h1>
        <Card>
          <CardContent className="py-10 text-center text-sm text-[var(--color-text-muted)]">
            Create a project first on the{' '}
            <Link to="/projects" className="text-[var(--color-accent)] underline">
              Projects
            </Link>{' '}
            page before uploading documents.
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-[var(--color-text)]">Documents</h1>
        <div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.xlsx,.pptx,.txt,.csv,.md"
            className="hidden"
            onChange={(e) => handleFilesSelected(e.target.files)}
          />
          <Button onClick={() => fileInputRef.current?.click()} disabled={!projectId || uploadMutation.isPending}>
            <Upload className="h-4 w-4" />
            {uploadMutation.isPending ? 'Uploading...' : 'Upload Documents'}
          </Button>
        </div>
      </div>

      {uploadError && <p className="mb-3 text-sm text-[var(--color-danger)]">{uploadError}</p>}

      {!projectId && !projectsLoading && (
        <p className="text-sm text-[var(--color-text-muted)]">Select a project in the top bar.</p>
      )}

      {isLoading && <p className="text-sm text-[var(--color-text-muted)]">Loading documents...</p>}

      {documents && documents.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-[var(--color-text-muted)]">
            No documents uploaded yet. Supported formats: PDF, DOCX, XLSX, PPTX, TXT, CSV, MD.
          </CardContent>
        </Card>
      )}

      {documents && documents.length > 0 && (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-[var(--color-border)] text-xs text-[var(--color-text-muted)]">
                <tr>
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Size</th>
                  <th className="px-4 py-2 font-medium">Pages/Blocks</th>
                  <th className="px-4 py-2 font-medium">Flags</th>
                  <th className="px-4 py-2 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id} className="border-b border-[var(--color-border)] last:border-0">
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        {doc.is_authoritative && (
                          <ShieldCheck className="h-3.5 w-3.5 text-[var(--color-accent)]" />
                        )}
                        <span className="text-[var(--color-text)]">{doc.filename}</span>
                      </div>
                      {doc.status === 'failed' && doc.error && (
                        <div className="mt-0.5 text-xs text-[var(--color-danger)]">{doc.error}</div>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <Badge tone={statusTone(doc.status)}>{doc.status}</Badge>
                    </td>
                    <td className="px-4 py-2 text-[var(--color-text-muted)]">{formatSize(doc.size_bytes)}</td>
                    <td className="px-4 py-2 text-[var(--color-text-muted)]">
                      {doc.page_count != null ? `${doc.page_count} pages, ` : ''}
                      {doc.block_count} blocks
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap gap-1">
                        {doc.status === 'completed' && (
                          <Badge
                            tone={doc.indexed ? 'success' : 'neutral'}
                            title={
                              doc.indexed
                                ? `Indexed into ${doc.indexed_chunk_count} chunk(s) for search`
                                : doc.index_error ?? 'Not yet indexed'
                            }
                          >
                            {doc.indexed ? `Indexed (${doc.indexed_chunk_count})` : 'Not indexed'}
                          </Badge>
                        )}
                        {doc.requires_ocr && (
                          <Badge tone="warning" title="Scanned pages need OCR">
                            OCR needed
                          </Badge>
                        )}
                        {doc.duplicate_of && (
                          <Badge tone="warning" title={`Exact duplicate of document ${doc.duplicate_of}`}>
                            <Copy className="mr-1 inline h-3 w-3" />
                            Duplicate
                          </Badge>
                        )}
                        {doc.possible_conflicts.length > 0 && (
                          <Badge tone="danger" title="Same filename, different content as another document">
                            <AlertTriangle className="mr-1 inline h-3 w-3" />
                            Conflict
                          </Badge>
                        )}
                        {doc.warnings.length > 0 && (
                          <Badge tone="warning" title={doc.warnings.join('\n')}>
                            {doc.warnings.length} warning{doc.warnings.length > 1 ? 's' : ''}
                          </Badge>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex justify-end gap-1">
                        {doc.status === 'completed' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setPreviewDoc(doc)}
                            title="Preview extracted content"
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </Button>
                        )}
                        <a href={`/api/projects/${projectId}/documents/${doc.id}/download`} title="Download original">
                          <Button variant="ghost" size="sm">
                            <Download className="h-3.5 w-3.5" />
                          </Button>
                        </a>
                        <Button
                          variant="ghost"
                          size="sm"
                          title={doc.is_authoritative ? 'Unmark as authoritative' : 'Mark as authoritative'}
                          onClick={() =>
                            authoritativeMutation.mutate({ documentId: doc.id, value: !doc.is_authoritative })
                          }
                        >
                          <ShieldCheck
                            className={`h-3.5 w-3.5 ${doc.is_authoritative ? 'text-[var(--color-accent)]' : ''}`}
                          />
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => {
                            if (confirm(`Delete "${doc.filename}"?`)) deleteMutation.mutate(doc.id)
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
        </Card>
      )}

      {previewDoc && projectId && (
        <DocumentPreviewDialog projectId={projectId} document={previewDoc} onClose={() => setPreviewDoc(null)} />
      )}

      {projectId && documents && documents.some((d) => d.status === 'completed') && (
        <RagSearchPanel projectId={projectId} />
      )}
    </div>
  )
}
