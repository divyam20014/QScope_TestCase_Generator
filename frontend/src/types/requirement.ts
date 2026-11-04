export type RequirementType =
  | 'functional'
  | 'business'
  | 'non_functional'
  | 'rule'
  | 'validation'
  | 'workflow'
  | 'role'
  | 'other'

export type ClassificationState = 'clear' | 'partial' | 'ambiguous' | 'conflicting' | 'missing' | 'not_testable'

export interface RequirementSource {
  document_id: string
  document_name: string
  page: number | null
  sheet: string | null
  section: string | null
  chunk_ids: number[]
}

export interface ClarificationItem {
  id: string
  project_id: string
  requirement_id: string
  question: string
  status: 'open' | 'resolved'
  created_at: string
  resolved_at: string | null
  resolution_note: string | null
}

export interface Requirement {
  id: string
  project_id: string
  source_id_hint: string | null
  text: string
  requirement_type: RequirementType
  classification_state: ClassificationState
  rationale: string | null
  source: RequirementSource
  created_at: string
  updated_at: string
}
