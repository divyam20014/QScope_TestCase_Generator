export type ProjectStatus = 'active' | 'archived'

export interface Project {
  id: string
  name: string
  description: string
  business_domain: string
  status: ProjectStatus
  created_at: string
  updated_at: string
  document_count: number
  requirement_count: number
  test_case_count: number
}

export interface ProjectCreatePayload {
  name: string
  description?: string
  business_domain?: string
}
