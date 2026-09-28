/**
 * api/graph.ts
 * Typed API client for all /api/graph/* endpoints.
 */
import client from './client'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface CytoscapeNode {
  data: {
    id: string
    label: string
    type: string
    value: string
    confidence: number
    risk_score: number
    evidence_ids: string[]
    attributes: Record<string, unknown>
  }
}

export interface CytoscapeEdge {
  data: {
    id: string
    source: string
    target: string
    relationship: string
    confidence: number
    evidence_source: string
    attributes: Record<string, unknown>
  }
}

export interface GraphResponse {
  case_id: string
  nodes: CytoscapeNode[]
  edges: CytoscapeEdge[]
  stats: { node_count: number; edge_count: number }
  message?: string
}

export interface NodeDetail {
  case_id: string
  entity_id: string
  type: string
  value: string
  label: string
  confidence: number
  risk_score: number
  attributes: Record<string, unknown>
  in_degree: number
  out_degree: number
  neighbors: Array<{ id: string; label: string; type: string; relationship: string }>
  evidence: unknown[]
}

export interface PathResult {
  case_id: string
  source: string
  target: string
  mode: string
  found: boolean
  path?: string[]
  nodes?: CytoscapeNode[]
  edges?: CytoscapeEdge[]
  paths?: Array<{ path: string[]; nodes: CytoscapeNode[]; edges: CytoscapeEdge[] }>
  message?: string
}

export interface SearchResult {
  case_id: string
  query: string
  nodes: CytoscapeNode[]
  total: number
}

export interface Component {
  id: number
  size: number
  nodes: string[]
  dominant_type: string
}

export interface ComponentsResult {
  case_id: string
  components: Component[]
  total: number
}

// ── API functions ─────────────────────────────────────────────────────────────

export const fetchGraph = (
  caseId: string,
  params?: {
    entity_types?: string
    rel_types?: string
    min_confidence?: number
    evidence_source?: string
    pattern?: string
  }
): Promise<GraphResponse> =>
  client.get(`/api/graph/${caseId}`, { params }).then((r) => r.data)

export const fetchNeighbors = (
  caseId: string,
  entityId: string,
  depth = 1,
  direction = 'both'
): Promise<GraphResponse & { entity_id: string; depth: number; direction: string }> =>
  client
    .get(`/api/graph/${caseId}/neighbors/${entityId}`, { params: { depth, direction } })
    .then((r) => r.data)

export const fetchPath = (
  caseId: string,
  source: string,
  target: string,
  mode: 'shortest' | 'transaction' = 'shortest'
): Promise<PathResult> =>
  client.get(`/api/graph/${caseId}/path`, { params: { source, target, mode } }).then((r) => r.data)

export const fetchNodeDetail = (caseId: string, entityId: string): Promise<NodeDetail> =>
  client.get(`/api/graph/${caseId}/node/${entityId}`).then((r) => r.data)

export const fetchSearch = (caseId: string, q: string): Promise<SearchResult> =>
  client.get(`/api/graph/${caseId}/search`, { params: { q } }).then((r) => r.data)

export const fetchComponents = (caseId: string): Promise<ComponentsResult> =>
  client.get(`/api/graph/${caseId}/components`).then((r) => r.data)
