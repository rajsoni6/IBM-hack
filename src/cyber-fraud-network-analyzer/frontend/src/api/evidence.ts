/**
 * api/evidence.ts
 * Typed API client for /api/evidence endpoints.
 */
import client from './client'

export interface EvidenceRecord {
  evidence_id: string
  case_id: string
  source_file: string
  source_record: Record<string, unknown>
  timestamp: string
  entities: string[]
  relationships: string[]
  description: string
  type: string
  collected_by: string
  is_verified: boolean
  hash_sha256: string
  chain?: {
    evidence: EvidenceRecord
    entities: unknown[]
    relationships: unknown[]
  }
}

export interface EvidenceListResponse {
  case_id: string
  evidence: EvidenceRecord[]
  count: number
}

export const listEvidence = (caseId: string): Promise<EvidenceListResponse> =>
  client.get(`/api/evidence/${caseId}`).then((r) => r.data)

export const getEvidence = (
  caseId: string,
  evidenceId: string
): Promise<EvidenceRecord> =>
  client.get(`/api/evidence/${caseId}/${evidenceId}`).then((r) => r.data)
