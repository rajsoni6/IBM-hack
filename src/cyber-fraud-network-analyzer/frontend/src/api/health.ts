import client from './client'

export interface HealthResponse {
  status: string
  service: string
  version: string
  environment: string
  ai_provider: string
  data_dir: string
  phase: number
  phases_complete: string[]
  phases_pending: string[]
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await client.get<HealthResponse>('/api/health')
  return res.data
}
