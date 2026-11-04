import type { TestCategory, TestType } from '@/types/testcase'

export type CoverageStatus = 'covered' | 'partial' | 'not_covered'

export interface RequirementCoverage {
  requirement_id: string
  status: CoverageStatus
  test_case_count: number
  categories_covered: TestCategory[]
  types_covered: TestType[]
  missing_categories: TestCategory[]
}

export interface ProjectCoverage {
  total_requirements: number
  covered: number
  partial: number
  not_covered: number
  coverage_percentage: number
  weighted_coverage_percentage: number
  per_requirement: RequirementCoverage[]
}

export interface TraceabilityRow {
  requirement_id: string
  requirement_text: string
  requirement_type: string
  classification_state: string
  coverage_status: string
  test_case_ids: string[]
}

export interface DuplicateGroup {
  method: 'exact' | 'normalized' | 'semantic'
  test_case_ids: string[]
  similarity: number | null
}

export interface QualityIssue {
  id: string
  project_id: string
  requirement_id: string
  test_case_id: string
  issue_type: string
  explanation: string
  suggested_fix: string | null
  status: 'open' | 'resolved'
  created_at: string
  resolved_at: string | null
  resolution_note: string | null
}
