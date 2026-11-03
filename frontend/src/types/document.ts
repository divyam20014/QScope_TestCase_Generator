export type DocumentStatus = 'processing' | 'completed' | 'failed'

export interface DocumentRecord {
  id: string
  project_id: string
  filename: string
  extension: string
  size_bytes: number
  content_hash: string
  status: DocumentStatus
  error: string | null
  warnings: string[]
  page_count: number | null
  requires_ocr: boolean
  block_count: number
  is_authoritative: boolean
  duplicate_of: string | null
  possible_conflicts: string[]
  indexed: boolean
  index_error: string | null
  indexed_chunk_count: number
  uploaded_at: string
  processed_at: string | null
}

export type BlockType = 'heading' | 'paragraph' | 'table' | 'list_item'

export interface ExtractedBlock {
  block_id: string
  type: BlockType
  text: string
  level: number | null
  page: number | null
  sheet: string | null
  section: string | null
  table_data: string[][] | null
}

export interface ExtractionWarning {
  message: string
  page: number | null
  sheet: string | null
}

export interface ExtractionResult {
  blocks: ExtractedBlock[]
  warnings: ExtractionWarning[]
  page_count: number | null
  requires_ocr: boolean
}
