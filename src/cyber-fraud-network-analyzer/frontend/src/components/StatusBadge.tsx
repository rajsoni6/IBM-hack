/**
 * components/StatusBadge.tsx
 * Reusable status/severity badge.
 */
interface Props {
  status: 'ok' | 'error' | 'warn' | 'info' | string
  label?: string
}

const MAP: Record<string, string> = {
  ok:     'badge-success',
  active: 'badge-success',
  error:  'badge-danger',
  high:   'badge-danger',
  warn:   'badge-warn',
  medium: 'badge-warn',
  info:   'badge-info',
  low:    'badge-info',
}

export default function StatusBadge({ status, label }: Props) {
  const cls = MAP[status.toLowerCase()] ?? 'badge-info'
  return <span className={cls}>{label ?? status}</span>
}
