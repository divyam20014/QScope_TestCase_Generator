export type TestType = 'business' | 'application' | 'system' | 'integration' | 'e2e' | 'security'

export type TestCategory = 'positive' | 'negative' | 'edge' | 'boundary' | 'destructive'

export type Priority = 'critical' | 'high' | 'medium' | 'low'

export interface TestCase {
  id: string
  project_id: string
  batch_id: string
  requirement_id: string
  scenario_id: string
  scenario_description: string
  title: string
  test_type: TestType
  test_category: TestCategory
  preconditions: string
  test_data: string
  steps: string[]
  expected_result: string
  priority: Priority
  source_document: string
  source_page: number | null
  source_section: string | null
  coverage_status: string
  assumptions: string | null
  assumption_status: string
  destructive: boolean
  approved: boolean
  locked: boolean
  manually_edited: boolean
  created_at: string
  updated_at: string
}

export interface ManualTestCaseCreate {
  requirement_id: string
  scenario_description: string
  title: string
  test_type: TestType
  test_category: TestCategory
  preconditions: string
  test_data: string
  steps: string[]
  expected_result: string
  priority: Priority
  source_document?: string
  source_page?: number | null
  source_section?: string | null
  assumptions?: string | null
}

export type TestCaseUpdate = Partial<
  Pick<
    TestCase,
    | 'scenario_description'
    | 'title'
    | 'test_type'
    | 'test_category'
    | 'preconditions'
    | 'test_data'
    | 'steps'
    | 'expected_result'
    | 'priority'
    | 'assumptions'
  >
>

export interface TestCaseVersionEntry {
  id: string
  test_case_id: string
  snapshot: TestCase
  created_at: string
}

export type JobStatus = 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'

export interface GenerationBatchSpec {
  batch_id: string
  requirement_id: string
  test_type: TestType
  test_category: TestCategory
}

export interface GenerationBatchResult {
  batch_id: string
  status: 'completed' | 'failed'
  test_case_count: number
  error: string | null
  completed_at: string | null
}

export interface GenerationJob {
  id: string
  project_id: string
  status: JobStatus
  requirement_ids: string[]
  test_types: TestType[]
  test_categories: TestCategory[]
  model: string | null
  batches: GenerationBatchSpec[]
  results: Record<string, GenerationBatchResult>
  next_batch_index: number
  error: string | null
  retry_after_seconds: number | null
  created_at: string
  updated_at: string
}
