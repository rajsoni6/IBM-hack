/**
 * api/patterns.ts
 * Typed API client for /api/patterns endpoints.
 */
import client from './client'

export interface PatternFinding {
  pattern_type: string
  pattern?: string
  confidence: number
  entities?: string[]
  affected_entities?: string[]
  indicators: string[]
  evidence_ids: string[]
}

export interface PatternsResponse {
  case_id: string
  analyzed_at: string
  total_findings: number
  findings: PatternFinding[]
  stats: {
    node_count: number
    edge_count: number
    tx_count: number
    call_count: number
  }
}

export interface RoleEntry {
  entity_id: string
  primary_role: string
  risk_score: number
  in_degree?: number
  out_degree?: number
  degree_centrality?: number
}

export interface RolesResponse {
  case_id: string
  analyzed_at: string
  total_entities: number
  role_summary: Record<string, number>
  roles: RoleEntry[]
}

export const getPatterns = (caseId: string): Promise<PatternsResponse | null> =>
  client.get(`/api/patterns/${caseId}`).then((r) => r.data)

export const runPatternAnalysis = (caseId: string): Promise<PatternsResponse> =>
  client.post(`/api/patterns/analyze/${caseId}`).then((r) => r.data)

export const getRoles = (caseId: string): Promise<RolesResponse | null> =>
  client.get(`/api/roles/${caseId}`).then((r) => r.data)

export const runRoleAnalysis = (caseId: string): Promise<RolesResponse> =>
  client.post(`/api/roles/analyze/${caseId}`).then((r) => r.data)
