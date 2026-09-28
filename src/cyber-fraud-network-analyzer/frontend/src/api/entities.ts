/**
 * api/entities.ts
 * Typed API client for /api/graph entity endpoints.
 */
import client from './client'

export interface Entity {
  entity_id: string
  type: string
  value: string
  label: string
  confidence: number
  risk_score: number
  case_ids: string[]
  evidence_ids: string[]
  attributes: Record<string, unknown>
  extracted_at: string
  updated_at: string
}

export interface EntitiesResponse {
  case_id: string
  nodes: Array<{ data: Entity }>
  stats: { node_count: number; edge_count: number }
}

export const listEntities = (caseId: string): Promise<EntitiesResponse> =>
  client.get(`/api/graph/${caseId}`).then((r) => r.data)
