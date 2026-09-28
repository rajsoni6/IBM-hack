/**
 * pages/Timeline.tsx
 * Chronological investigation timeline with event type filtering.
 */
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import { getTimeline, type TimelineEvent } from '../api/timeline'

const EVENT_TYPES = ['all', 'transaction', 'call', 'sim_event', 'device_association', 'account_activity', 'case_event']

const EVENT_COLORS: Record<string, string> = {
  transaction:         'bg-blue-100 text-blue-700 border-blue-200',
  call:                'bg-purple-100 text-purple-700 border-purple-200',
  sim_event:           'bg-orange-100 text-orange-700 border-orange-200',
  device_association:  'bg-teal-100 text-teal-700 border-teal-200',
  account_activity:    'bg-green-100 text-green-700 border-green-200',
  case_event:          'bg-gray-100 text-gray-700 border-gray-200',
  ip_event:            'bg-red-100 text-red-700 border-red-200',
}

const EVENT_ICONS: Record<string, string> = {
  transaction:        '💳',
  call:               '📞',
  sim_event:          '📶',
  device_association: '📱',
  account_activity:   '🏦',
  case_event:         '📁',
  ip_event:           '🌐',
}

function fmtTs(ts: string): string {
  try {
    return new Date(ts).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return ts
  }
}

export default function Timeline() {
  const [events,  setEvents]  = useState<TimelineEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)
  const [caseId,  setCaseId]  = useState('case_001')
  const [filter,  setFilter]  = useState('all')

  const load = (id: string) => {
    setLoading(true)
    getTimeline(id)
      .then((r) => setEvents(r.events))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => load(caseId), [caseId])

  const visible = filter === 'all'
    ? events
    : events.filter((e) => e.event_type === filter)

  return (
    <div>
      <PageHeader
        title="Investigation Timeline"
        subtitle="Chronological view of all case events"
      />
      <div className="px-8 py-6 space-y-5">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">⚠ {error}</div>
        )}

        {/* Controls */}
        <div className="card p-4 flex flex-wrap gap-3 items-center">
          <div>
            <label className="text-xs font-medium text-gray-500 mr-2">Case ID</label>
            <input
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-40"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') load(caseId) }}
            />
            <button className="ml-2 btn-secondary text-xs py-1" onClick={() => load(caseId)}>
              Load
            </button>
          </div>
          <div className="flex gap-1 flex-wrap">
            {EVENT_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setFilter(t)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                  filter === t
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {t === 'all' ? 'All' : t.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Stats */}
        <div className="flex gap-4 flex-wrap">
          {Object.entries(
            events.reduce((acc, e) => ({ ...acc, [e.event_type]: (acc[e.event_type] || 0) + 1 }), {} as Record<string, number>)
          ).map(([type, count]) => (
            <div key={type} className={`px-3 py-1.5 rounded-full text-xs font-medium border ${EVENT_COLORS[type] ?? 'bg-gray-100 text-gray-600 border-gray-200'}`}>
              {EVENT_ICONS[type] ?? '•'} {type.replace(/_/g, ' ')}: {count}
            </div>
          ))}
        </div>

        {/* Timeline */}
        <div className="card">
          {loading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse text-sm">Loading timeline…</div>
          ) : visible.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">No events found for this case / filter.</div>
          ) : (
            <div className="relative p-6">
              {/* Vertical spine */}
              <div className="absolute left-10 top-0 bottom-0 w-0.5 bg-gray-200" />
              <div className="space-y-6">
                {visible.map((ev) => {
                  const colorClass = EVENT_COLORS[ev.event_type] ?? 'bg-gray-100 text-gray-600 border-gray-200'
                  const icon       = EVENT_ICONS[ev.event_type] ?? '•'
                  return (
                    <div key={ev.event_id} className="flex gap-4 relative">
                      {/* Dot */}
                      <div className={`relative z-10 w-8 h-8 rounded-full flex items-center justify-center text-base shrink-0 border ${colorClass}`}>
                        {icon}
                      </div>
                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm font-medium text-gray-800 leading-snug">
                            {ev.description}
                          </p>
                          <span className="text-xs text-gray-400 shrink-0">{fmtTs(ev.timestamp)}</span>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`text-xs px-2 py-0.5 rounded-full border ${colorClass}`}>
                            {ev.event_type.replace(/_/g, ' ')}
                          </span>
                          {ev.entity_ids?.length > 0 && (
                            <span className="text-xs text-gray-400">
                              Entities: {ev.entity_ids.join(', ')}
                            </span>
                          )}
                          {ev.evidence_id && (
                            <span className="text-xs text-blue-500">📎 {ev.evidence_id}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
