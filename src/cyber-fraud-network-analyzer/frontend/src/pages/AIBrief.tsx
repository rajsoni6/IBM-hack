/**
 * pages/AIBrief.tsx
 * FIR-ready AI case brief with generate / print / download controls.
 */
import { useState } from 'react'
import PageHeader from '../components/PageHeader'
import { generateSummary, getSummary, type InvestigationSummary } from '../api/summary'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="break-inside-avoid mb-6">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-b border-gray-200 pb-1 mb-3">
        {title}
      </h3>
      {children}
    </div>
  )
}

function KVRow({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null || value === '') return null
  return (
    <div className="flex gap-2 text-sm">
      <span className="text-gray-500 w-36 shrink-0">{label}</span>
      <span className="text-gray-800">{String(value)}</span>
    </div>
  )
}

function ConfidencePill({ level }: { level: string }) {
  const map: Record<string, string> = {
    observed_evidence:      'bg-green-100 text-green-700',
    inferred_relationship:  'bg-yellow-100 text-yellow-700',
    model_prediction:       'bg-orange-100 text-orange-700',
    investigator_conclusion:'bg-purple-100 text-purple-700',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[level] ?? 'bg-gray-100 text-gray-500'}`}>
      {level?.replace(/_/g, ' ')}
    </span>
  )
}

export default function AIBrief() {
  const [summary,    setSummary]    = useState<InvestigationSummary | null>(null)
  const [caseId,     setCaseId]     = useState('case_001')
  const [generating, setGenerating] = useState(false)
  const [error,      setError]      = useState<string | null>(null)

  const generate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const r = await generateSummary(caseId)
      setSummary(r)
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setGenerating(false)
    }
  }

  const load = async () => {
    try {
      const r = await getSummary(caseId)
      setSummary(r)
    } catch {
      setSummary(null)
    }
  }

  const downloadJson = () => {
    if (!summary) return
    const blob = new Blob([JSON.stringify(summary, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${summary.case_id}_summary.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const s = summary?.sections

  return (
    <div>
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          .card { border: 1px solid #e5e7eb !important; box-shadow: none !important; }
        }
      `}</style>

      <div className="no-print">
        <PageHeader
          title="AI Case Brief"
          subtitle="FIR-ready investigation summary (AI-generated draft)"
          actions={
            <div className="flex gap-2 items-center">
              <input
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-40"
                value={caseId}
                onChange={(e) => setCaseId(e.target.value)}
                placeholder="Case ID"
              />
              <button className="btn-secondary text-sm" onClick={load}>
                Load Stored
              </button>
              <button className="btn-primary text-sm" onClick={generate} disabled={generating}>
                {generating ? 'Generating…' : summary ? '↺ Regenerate' : '▶ Generate'}
              </button>
              {summary && (
                <>
                  <button className="btn-secondary text-sm" onClick={downloadJson}>
                    ↓ JSON
                  </button>
                  <button className="btn-secondary text-sm" onClick={() => window.print()}>
                    🖨 Print / PDF
                  </button>
                </>
              )}
            </div>
          }
        />
      </div>

      <div className="px-8 py-6 space-y-5 max-w-5xl">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 no-print">
            ⚠ {error}
          </div>
        )}

        {!summary ? (
          <div className="card p-12 text-center text-gray-400 no-print">
            <p className="text-4xl mb-3">📄</p>
            <p className="text-sm">Enter a Case ID and click Generate to create an AI investigation brief.</p>
          </div>
        ) : (
          <div className="card p-8 space-y-6">
            {/* Disclaimer banner */}
            <div className="bg-red-50 border-2 border-red-300 rounded-lg p-4 text-center">
              <p className="font-bold text-red-800 text-sm">
                ⚠ AI-GENERATED DRAFT — REQUIRES INVESTIGATOR VERIFICATION
              </p>
              <p className="text-xs text-red-700 mt-1">{summary.disclaimer}</p>
            </div>

            {/* Document header */}
            <div className="border-b border-gray-200 pb-4">
              <p className="text-xs text-gray-400 uppercase tracking-widest">
                Cyber Fraud Investigation — Case Brief
              </p>
              <h1 className="text-xl font-bold text-gray-900 mt-1">
                {(s?.incident_summary as any)?.title ?? summary.case_id}
              </h1>
              <div className="flex gap-4 mt-2 flex-wrap">
                <KVRow label="Case ID"  value={summary.case_id} />
                <KVRow label="Generated" value={new Date(summary.generated_at).toLocaleString()} />
                <KVRow label="Provider" value={summary.provider} />
              </div>
            </div>

            {/* Incident Summary */}
            {s?.incident_summary && (
              <Section title="Incident Summary">
                <div className="space-y-1">
                  <KVRow label="Fraud Pattern" value={(s.incident_summary as any).fraud_pattern?.replace(/_/g, ' ')} />
                  <KVRow label="Severity"       value={(s.incident_summary as any).severity} />
                  <KVRow label="Status"         value={(s.incident_summary as any).status} />
                  <KVRow label="Jurisdiction"   value={(s.incident_summary as any).jurisdiction} />
                  <KVRow label="Assigned To"    value={(s.incident_summary as any).assigned_to} />
                  <KVRow label="Estimated Loss" value={
                    (s.incident_summary as any).total_loss_inr
                      ? `₹${Number((s.incident_summary as any).total_loss_inr).toLocaleString()}`
                      : undefined
                  } />
                  <KVRow label="Patterns Found" value={(s.incident_summary as any).patterns_detected} />
                  <div className="mt-2">
                    <ConfidencePill level={(s.incident_summary as any).confidence} />
                  </div>
                  <p className="text-sm text-gray-700 mt-2">{(s.incident_summary as any).note}</p>
                </div>
              </Section>
            )}

            {/* Victim Summary */}
            {s?.victim_summary && (
              <Section title="Victim Summary">
                <KVRow label="Victim Count" value={(s.victim_summary as any).victim_count} />
                <KVRow label="Victim IDs"   value={(s.victim_summary as any).victim_ids?.join(', ')} />
                <ConfidencePill level={(s.victim_summary as any).confidence} />
              </Section>
            )}

            {/* Transaction Summary */}
            {s?.transaction_summary && (
              <Section title="Transaction Summary">
                <KVRow label="Timeline Events"  value={(s.transaction_summary as any).transaction_event_count} />
                <KVRow label="Graph Transactions" value={(s.transaction_summary as any).graph_tx_count} />
                <KVRow label="Flagged Patterns" value={(s.transaction_summary as any).flagged_patterns} />
                {(s.transaction_summary as any).pattern_names?.length > 0 && (
                  <KVRow label="Pattern Types" value={(s.transaction_summary as any).pattern_names.join(', ')} />
                )}
                <p className="text-sm text-gray-700 mt-2">{(s.transaction_summary as any).note}</p>
              </Section>
            )}

            {/* Network Summary */}
            {s?.network_summary && (
              <Section title="Network Summary">
                <KVRow label="Nodes" value={(s.network_summary as any).node_count} />
                <KVRow label="Edges" value={(s.network_summary as any).edge_count} />
                <KVRow label="Entities" value={(s.network_summary as any).entity_count} />
                <ConfidencePill level={(s.network_summary as any).confidence} />
              </Section>
            )}

            {/* Timeline Summary */}
            {s?.timeline_summary && (
              <Section title="Timeline Summary">
                <KVRow label="Total Events" value={(s.timeline_summary as any).total_events} />
                <KVRow label="First Event"  value={(s.timeline_summary as any).first_event} />
                <KVRow label="Last Event"   value={(s.timeline_summary as any).last_event} />
              </Section>
            )}

            {/* Detected Patterns */}
            {Array.isArray(s?.detected_patterns) && s.detected_patterns.length > 0 && (
              <Section title={`Detected Patterns (${s.detected_patterns.length})`}>
                <div className="space-y-3">
                  {(s.detected_patterns as any[]).map((p, i) => (
                    <div key={i} className="bg-gray-50 rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-gray-800 capitalize">
                          {p.pattern_type?.replace(/_/g, ' ')}
                        </span>
                        <span className="text-xs text-gray-500">
                          {(p.confidence * 100).toFixed(0)}% confidence
                        </span>
                        <ConfidencePill level={p.source_label} />
                      </div>
                      {p.affected_entities?.length > 0 && (
                        <p className="text-xs text-gray-500">
                          Entities: {p.affected_entities.join(', ')}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* ML Analysis */}
            {s?.ml_analysis && (
              <Section title="ML Analysis">
                <KVRow label="Predictions Run"  value={(s.ml_analysis as any).predictions_run} />
                <KVRow label="High-Risk Entities" value={(s.ml_analysis as any).high_risk_entities} />
                <KVRow label="Model Version"    value={(s.ml_analysis as any).model_version} />
                <ConfidencePill level="model_prediction" />
                <p className="text-xs text-orange-700 bg-orange-50 rounded-lg p-2 mt-2">
                  {(s.ml_analysis as any).disclaimer}
                </p>
              </Section>
            )}

            {/* Key Evidence */}
            {Array.isArray(s?.key_evidence) && s.key_evidence.length > 0 && (
              <Section title={`Key Evidence (${s.key_evidence.length})`}>
                <div className="space-y-2">
                  {(s.key_evidence as any[]).map((e, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm">
                      <span className="text-green-600 mt-0.5">
                        {e.is_verified ? '✓' : '○'}
                      </span>
                      <div>
                        <span className="font-medium text-gray-700">{e.type}</span>
                        {e.description && (
                          <span className="text-gray-500 ml-2">— {e.description.slice(0, 100)}</span>
                        )}
                        <ConfidencePill level={e.confidence} />
                      </div>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Open Questions */}
            {Array.isArray(s?.open_questions) && s.open_questions.length > 0 && (
              <Section title="Open Questions">
                <ul className="space-y-1">
                  {(s.open_questions as string[]).map((q, i) => (
                    <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                      <span className="text-red-400 shrink-0">○</span>
                      {q}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* Recommended Actions */}
            {Array.isArray(s?.recommended_actions) && s.recommended_actions.length > 0 && (
              <Section title="Recommended Actions">
                <ol className="space-y-1 list-decimal list-inside">
                  {(s.recommended_actions as string[]).map((a, i) => (
                    <li key={i} className="text-sm text-gray-700">{a}</li>
                  ))}
                </ol>
              </Section>
            )}

            {/* Limitations */}
            {Array.isArray(s?.limitations) && s.limitations.length > 0 && (
              <Section title="Limitations & Caveats">
                <ul className="space-y-1">
                  {(s.limitations as string[]).map((l, i) => (
                    <li key={i} className="text-xs text-gray-500 flex items-start gap-2">
                      <span className="shrink-0">⚠</span>
                      {l}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* Footer */}
            <div className="border-t border-gray-200 pt-4 text-xs text-gray-400 text-center">
              Generated by Cyber Fraud Network Analyzer · {summary.generated_at} ·
              Case {summary.case_id}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
