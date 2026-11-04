export type AIProvider = 'gemini' | 'openai' | 'anthropic'

export interface ModelCapability {
  model_id: string
  provider: AIProvider
  display_name: string
  description: string
  supports_structured_output: boolean
  context_window_tokens: number
  is_default: boolean
}

export interface AIConfig {
  selected_model: string
  temperature: number
  max_output_tokens: number
  updated_at: string
}

export interface AIConfigUpdate {
  selected_model?: string
  temperature?: number
  max_output_tokens?: number
}

export interface ConnectionTestResult {
  success: boolean
  model: string
  latency_ms: number | null
  error: string | null
  tested_at: string
}

export interface UsageRecord {
  model: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  request_count: number
  last_used_at: string | null
}

export interface UsageStats {
  by_model: Record<string, UsageRecord>
  total_requests: number
  total_tokens: number
}
