export interface RagChunk {
  chunk_id: number
  project_id: string
  document_id: string
  document_name: string
  page: number | null
  sheet: string | null
  section: string | null
  text: string
  requirement_id: string | null
}

export interface RagSearchHit {
  chunk: RagChunk
  score: number
  semantic_score: number | null
  keyword_score: number | null
}

export interface RagStats {
  chunk_count: number
  indexed_document_count: number
  completed_document_count: number
}
