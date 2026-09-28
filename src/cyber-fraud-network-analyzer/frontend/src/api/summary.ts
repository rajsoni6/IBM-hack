/**
 * api/summary.ts
 * Typed API client for /api/summary endpoints.
 */
import client from './client'

export interface SummarySections {
  incident_summary: Record<string, unknown>
  victim_summary: Record<string, unknown>
  transaction_summary: Record<string, unknown>
  network_summary: Record<string, unknown>
  timeline_summary: Record<string, unknown>
  detected_patterns: unknown[]
  ml_analysis: Record<string, unknown>
  network_roles: unknown[]
  key_evidence: unknown[]
  open_questions: string[]
  recommended_actions: string[]
  limitations: string[]
}

export interface InvestigationSummary {
  summary_id: string
  case_id: string
  generated_at: string
  provider: string
  version: string
  disclaimer: string
  sections: SummarySections
}

export const generateSummary = (caseId: string): Promise<InvestigationSummary> =>
  client.post(`/api/summary/generate/${caseId}`).then((r) => r.data)

export const getSummary = (caseId: string): Promise<InvestigationSummary> =>
  client.get(`/api/summary/${caseId}`).then((r) => r.data)
