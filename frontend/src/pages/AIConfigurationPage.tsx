import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import type { AIConfig, ConnectionTestResult, ModelCapability, UsageStats } from '@/types/ai'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Wifi, XCircle } from 'lucide-react'
import { useState } from 'react'

function ModelConfigForm({ config, models }: { config: AIConfig; models: ModelCapability[] }) {
  const queryClient = useQueryClient()
  const [selectedModel, setSelectedModel] = useState(config.selected_model)
  const [temperature, setTemperature] = useState(config.temperature)
  const [maxOutputTokens, setMaxOutputTokens] = useState(config.max_output_tokens)
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null)

  const saveMutation = useMutation({
    mutationFn: () =>
      api.put<AIConfig>('/ai/config', {
        selected_model: selectedModel,
        temperature,
        max_output_tokens: maxOutputTokens,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai-config'] }),
  })

  const testMutation = useMutation({
    mutationFn: () => api.post<ConnectionTestResult>('/ai/test-connection'),
    onSuccess: (result) => setTestResult(result),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Gemini Model</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {models.map((model) => (
          <label
            key={model.model_id}
            className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 text-sm transition-colors ${
              selectedModel === model.model_id
                ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/5'
                : 'border-[var(--color-border)]'
            }`}
          >
            <input
              type="radio"
              className="mt-1"
              checked={selectedModel === model.model_id}
              onChange={() => setSelectedModel(model.model_id)}
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium text-[var(--color-text)]">{model.display_name}</span>
                <Badge tone="neutral">{model.provider}</Badge>
                {model.is_default && <Badge tone="success">default</Badge>}
              </div>
              <p className="mt-0.5 text-[var(--color-text-muted)]">{model.description}</p>
              <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                Context window: {model.context_window_tokens.toLocaleString()} tokens
              </p>
            </div>
          </label>
        ))}

        <div className="grid grid-cols-2 gap-3 pt-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Temperature</label>
            <Input
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={temperature}
              onChange={(e) => setTemperature(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
              Max output tokens
            </label>
            <Input
              type="number"
              min={1}
              max={65536}
              value={maxOutputTokens}
              onChange={(e) => setMaxOutputTokens(Number(e.target.value))}
            />
          </div>
        </div>

        <div className="flex gap-2 pt-2">
          <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? 'Saving...' : 'Save'}
          </Button>
          <Button variant="secondary" onClick={() => testMutation.mutate()} disabled={testMutation.isPending}>
            <Wifi className="h-4 w-4" />
            {testMutation.isPending ? 'Testing...' : 'Test Connection'}
          </Button>
        </div>
        {saveMutation.isSuccess && <p className="text-xs text-[var(--color-success)]">Saved.</p>}

        {testResult && (
          <div
            className={`flex items-start gap-2 rounded-md border p-3 text-sm ${
              testResult.success
                ? 'border-[var(--color-success)]/40 bg-[var(--color-success)]/5'
                : 'border-[var(--color-danger)]/40 bg-[var(--color-danger)]/5'
            }`}
          >
            {testResult.success ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-success)]" />
            ) : (
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-danger)]" />
            )}
            <div>
              <div className="font-medium text-[var(--color-text)]">
                {testResult.success ? 'Connected' : 'Connection failed'}
              </div>
              <div className="text-[var(--color-text-muted)]">
                Model: {testResult.model}
                {testResult.latency_ms != null && ` - ${testResult.latency_ms}ms`}
              </div>
              {testResult.error && <div className="mt-1 text-[var(--color-danger)]">{testResult.error}</div>}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function UsagePanel({ usage }: { usage: UsageStats | undefined }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Usage</CardTitle>
      </CardHeader>
      <CardContent>
        {!usage || usage.total_requests === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)]">No Gemini calls recorded yet.</p>
        ) : (
          <div className="space-y-3 text-sm">
            <div className="text-[var(--color-text-muted)]">
              {usage.total_requests} request{usage.total_requests === 1 ? '' : 's'},{' '}
              {usage.total_tokens.toLocaleString()} total tokens
            </div>
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-[var(--color-text-muted)]">
                <tr>
                  <th className="py-1 font-medium">Model</th>
                  <th className="py-1 font-medium">Requests</th>
                  <th className="py-1 font-medium">Prompt</th>
                  <th className="py-1 font-medium">Completion</th>
                  <th className="py-1 font-medium">Total</th>
                </tr>
              </thead>
              <tbody>
                {Object.values(usage.by_model).map((record) => (
                  <tr key={record.model} className="border-t border-[var(--color-border)]">
                    <td className="py-1 text-[var(--color-text)]">{record.model}</td>
                    <td className="py-1 text-[var(--color-text-muted)]">{record.request_count}</td>
                    <td className="py-1 text-[var(--color-text-muted)]">{record.prompt_tokens.toLocaleString()}</td>
                    <td className="py-1 text-[var(--color-text-muted)]">
                      {record.completion_tokens.toLocaleString()}
                    </td>
                    <td className="py-1 text-[var(--color-text-muted)]">{record.total_tokens.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function AIConfigurationPage() {
  const { data: models } = useQuery({
    queryKey: ['ai-models'],
    queryFn: () => api.get<ModelCapability[]>('/ai/models'),
  })
  const { data: config, isLoading } = useQuery({
    queryKey: ['ai-config'],
    queryFn: () => api.get<AIConfig>('/ai/config'),
  })
  const { data: usage } = useQuery({
    queryKey: ['ai-usage'],
    queryFn: () => api.get<UsageStats>('/ai/usage'),
  })

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">AI Configuration</h1>

      {isLoading && <p className="text-sm text-[var(--color-text-muted)]">Loading...</p>}

      {!isLoading && config && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ModelConfigForm config={config} models={models ?? []} />
          <UsagePanel usage={usage} />
        </div>
      )}
    </div>
  )
}
