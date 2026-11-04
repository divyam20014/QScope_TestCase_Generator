import type { TestCategory, TestType } from '@/types/testcase'

export type ExportFormat = 'xlsx' | 'docx' | 'pdf' | 'csv' | 'json'

export interface ExportScope {
  requirement_ids?: string[] | null
  test_types?: TestType[] | null
  test_categories?: TestCategory[] | null
}

export interface ExportRecord {
  id: string
  project_id: string
  format: ExportFormat
  filename: string
  size_bytes: number
  scope: ExportScope
  test_case_count: number
  created_at: string
}
