import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import type { RagSearchHit, RagStats } from '@/types/rag'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useState } from 'react'

export function RagSearchPanel({ projectId }: { projectId: string }) {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<'hybrid' | 'semantic' | 'keyword'>('hybrid')

  const { data: stats } = useQuery({
    queryKey: ['rag-stats', projectId],
    queryFn: () => api.get<RagStats>(`/projects/${projectId}/rag/stats`),
  })

  const searchMutation = useMutation({
    mutationFn: () =>
      api.get<RagSearchHit[]>(
        `/projects/${projectId}/rag/search?q=${encodeURIComponent(query)}&mode=${mode}&top_k=5`,
      ),
  })

  return (
    <Card className="mt-6">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Test Retrieval (RAG)</CardTitle>
        {stats && (
          <span className="text-xs text-[var(--color-text-muted)]">
            {stats.chunk_count} chunks indexed from {stats.indexed_document_count} document(s)
          </span>
        )}
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. What happens if a payment fails?"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && query.trim()) searchMutation.mutate()
            }}
          />
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as typeof mode)}
            className="h-10 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-sm"
          >
            <option value="hybrid">Hybrid</option>
            <option value="semantic">Semantic</option>
            <option value="keyword">Keyword</option>
          </select>
          <Button
            onClick={() => searchMutation.mutate()}
            disabled={!query.trim() || searchMutation.isPending}
          >
            <Search className="h-4 w-4" />
            Search
          </Button>
        </div>

        {searchMutation.isPending && (
          <p className="text-sm text-[var(--color-text-muted)]">Searching...</p>
        )}

        {searchMutation.isSuccess && searchMutation.data.length === 0 && (
          <p className="text-sm text-[var(--color-text-muted)]">No matching content found.</p>
        )}

        {searchMutation.isSuccess && searchMutation.data.length > 0 && (
          <div className="space-y-3">
            {searchMutation.data.map((hit) => (
              <div
                key={hit.chunk.chunk_id}
                className="rounded-md border border-[var(--color-border)] p-3 text-sm"
              >
                <div className="mb-1 flex items-center justify-between text-xs text-[var(--color-text-muted)]">
                  <span>
                    {hit.chunk.document_name}
                    {hit.chunk.page != null && ` · p.${hit.chunk.page}`}
                    {hit.chunk.sheet && ` · sheet: ${hit.chunk.sheet}`}
                    {hit.chunk.section && ` · ${hit.chunk.section}`}
                  </span>
                  <Badge tone="neutral">score {hit.score.toFixed(2)}</Badge>
                </div>
                <p className="text-[var(--color-text)]">{hit.chunk.text}</p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
