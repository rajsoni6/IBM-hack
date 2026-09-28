/**
 * api/timeline.ts
 * Typed API client for /api/timeline endpoints.
 */
import client from './client'

export interface TimelineEvent {
  event_id: string
  timestamp: string
  event_type:
    | 'transaction'
    | 'call'
    | 'sim_event'
    | 'device_association'
    | 'account_activity'
    | 'ip_event'
    | 'case_event'
  entity_ids: string[]
  description: string
  source: string
  evidence_id: string | null
}

export interface TimelineResponse {
  case_id: string
  events: TimelineEvent[]
  count: number
}

export const getTimeline = (caseId: string): Promise<TimelineResponse> =>
  client.get(`/api/timeline/${caseId}`).then((r) => r.data)
