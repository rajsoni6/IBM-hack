/**
 * components/EvidenceChain.tsx
 * Renders the chain: Finding → Evidence → Source Record → Entities → Relationships
 */
import type { EvidenceRecord } from '../api/evidence'

interface Props {
  evidence: EvidenceRecord
}

export default function EvidenceChain({ evidence }: Props) {
  const chain = evidence.chain

  return (
    <div className="space-y-4">
      {/* Evidence node */}
      <ChainNode
        color="blue"
        label="Evidence"
        title={evidence.type || evidence.evidence_id}
        meta={[
          evidence.description,
          evidence.collected_by ? `Collected by: ${evidence.collected_by}` : null,
          evidence.timestamp ? `At: ${evidence.timestamp}` : null,
          evidence.is_verified ? '✓ Verified' : '⚠ Unverified',
        ]}
      />

      {/* Entities */}
      {chain && chain.entities.length > 0 && (
        <div className="ml-6 border-l-2 border-blue-200 pl-4 space-y-2">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Linked Entities ({chain.entities.length})
          </p>
          {chain.entities.map((ent: any) => (
            <ChainNode
              key={ent.entity_id || ent.id}
              color="green"
              label={ent.type || 'Entity'}
              title={ent.value || ent.label || ent.entity_id}
              meta={[
                ent.risk_score !== undefined
                  ? `Risk: ${(ent.risk_score * 100).toFixed(0)}%`
                  : null,
              ]}
            />
          ))}
        </div>
      )}

      {/* Relationships */}
      {chain && chain.relationships.length > 0 && (
        <div className="ml-6 border-l-2 border-purple-200 pl-4 space-y-2">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Linked Relationships ({chain.relationships.length})
          </p>
          {chain.relationships.map((rel: any) => (
            <ChainNode
              key={rel.relationship_id || rel.id}
              color="purple"
              label={rel.relationship || 'Relationship'}
              title={`${rel.source_entity || ''} → ${rel.target_entity || ''}`}
              meta={[
                rel.confidence ? `Confidence: ${(rel.confidence * 100).toFixed(0)}%` : null,
              ]}
            />
          ))}
        </div>
      )}

      {/* Source record */}
      {evidence.source_file && (
        <div className="ml-6 border-l-2 border-gray-200 pl-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
            Source File
          </p>
          <p className="text-xs font-mono text-gray-600">{evidence.source_file}</p>
        </div>
      )}
    </div>
  )
}

// ── Internal sub-component ────────────────────────────────────────────────────

const COLOR_MAP: Record<string, string> = {
  blue:   'border-blue-400 bg-blue-50',
  green:  'border-green-400 bg-green-50',
  purple: 'border-purple-400 bg-purple-50',
  gray:   'border-gray-300 bg-gray-50',
}

function ChainNode({
  color,
  label,
  title,
  meta,
}: {
  color: string
  label: string
  title: string
  meta: (string | null)[]
}) {
  const cls = COLOR_MAP[color] ?? COLOR_MAP.gray
  return (
    <div className={`rounded-lg border-l-4 p-3 ${cls}`}>
      <div className="flex items-baseline gap-2">
        <span className="text-xs font-bold text-gray-500 uppercase">{label}</span>
        <span className="text-sm font-medium text-gray-800">{title}</span>
      </div>
      {meta.filter(Boolean).map((m, i) => (
        <p key={i} className="text-xs text-gray-600 mt-0.5">
          {m}
        </p>
      ))}
    </div>
  )
}
