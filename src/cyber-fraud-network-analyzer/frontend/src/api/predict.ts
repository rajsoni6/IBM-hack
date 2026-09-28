/**
 * api/predict.ts
 * Typed API client for /api/predict endpoint.
 */
import client from './client'

export interface PredictFeatures {
  tx_count?: number
  tx_out_count?: number
  tx_in_count?: number
  total_volume?: number
  out_volume?: number
  in_volume?: number
  avg_tx_amount?: number
  max_tx_amount?: number
  min_tx_amount?: number
  std_tx_amount?: number
  fwd_ratio?: number
  unique_peers?: number
  unique_out_peers?: number
  unique_in_peers?: number
  round_amount_ratio_out?: number
  near_threshold_ratio?: number
  suspicious_desc_ratio?: number
  self_loop_count?: number
  out_max_amount?: number
  [key: string]: number | undefined
}

export interface TopFeature {
  feature: string
  value: number
  importance: number
}

export interface PredictionResult {
  prediction_id: string
  case_id: string
  entity_id: string
  model_version: string
  timestamp: string
  risk_score: number
  classification: 'HIGH_RISK' | 'MEDIUM_RISK' | 'LOW_RISK' | 'VERY_LOW_RISK'
  top_features: TopFeature[]
  explanation: string
}

export const runPrediction = (
  features: PredictFeatures,
  caseId?: string,
  entityId?: string
): Promise<PredictionResult> =>
  client
    .post('/api/predict', { features, case_id: caseId ?? '', entity_id: entityId ?? '' })
    .then((r) => r.data)
