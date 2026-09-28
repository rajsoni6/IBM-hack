/**
 * api/cases.ts
 * Typed API client for /api/cases endpoints.
 */
import client from './client'

export interface Case {
  id: string
  title: string
  description: string
  fraud_pattern: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  status: 'open' | 'under_investigation' | 'closed' | 'chargesheeted' | 'archived'
  jurisdiction: string
  assigned_to: string
  total_loss_inr: number
  victim_ids: string[]
  suspect_ids: string[]
  tags: string[]
  created_by: string
  created_at: string
  updated_at: string
  closed_at: string | null
}

export interface CasesResponse {
  cases: Case[]
  total: number
  limit: number
  offset: number
}

export interface CreateCasePayload {
  title: string
  description?: string
  fraud_pattern?: string
  severity?: string
  status?: string
  jurisdiction?: string
  assigned_to?: string
  total_loss_inr?: number
}

export const listCases = (params?: {
  status?: string
  severity?: string
  fraud_pattern?: string
  limit?: number
  offset?: number
}): Promise<CasesResponse> =>
  client.get('/api/cases/', { params }).then((r) => r.data)

export const getCase = (id: string): Promise<{ case: Case }> =>
  client.get(`/api/cases/${id}`).then((r) => r.data)

export const createCase = (payload: CreateCasePayload): Promise<{ case: Case }> =>
  client.post('/api/cases/', payload).then((r) => r.data)

export const updateCase = (
  id: string,
  payload: Partial<CreateCasePayload>
): Promise<{ case: Case }> =>
  client.put(`/api/cases/${id}`, payload).then((r) => r.data)
