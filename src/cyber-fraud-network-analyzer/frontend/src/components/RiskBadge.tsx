/**
 * components/RiskBadge.tsx
 * Displays a colour-coded risk score badge.
 */
interface Props {
  score?: number
  classification?: string
}

const CLASSIFICATION_MAP: Record<string, { cls: string; label: string }> = {
  HIGH_RISK:      { cls: 'bg-red-100 text-red-700',    label: 'High Risk' },
  MEDIUM_RISK:    { cls: 'bg-orange-100 text-orange-700', label: 'Medium Risk' },
  LOW_RISK:       { cls: 'bg-yellow-100 text-yellow-700', label: 'Low Risk' },
  VERY_LOW_RISK:  { cls: 'bg-green-100 text-green-700',   label: 'Very Low Risk' },
}

function scoreToClass(score: number): string {
  if (score >= 0.8) return 'HIGH_RISK'
  if (score >= 0.5) return 'MEDIUM_RISK'
  if (score >= 0.2) return 'LOW_RISK'
  return 'VERY_LOW_RISK'
}

export default function RiskBadge({ score, classification }: Props) {
  const key = classification ?? (score !== undefined ? scoreToClass(score) : 'VERY_LOW_RISK')
  const { cls, label } = CLASSIFICATION_MAP[key] ?? CLASSIFICATION_MAP['VERY_LOW_RISK']
  const display = score !== undefined ? `${label} (${(score * 100).toFixed(0)}%)` : label
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {display}
    </span>
  )
}
