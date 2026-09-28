/**
 * components/StatCard.tsx
 * A metric card used on the Dashboard.
 */
interface Props {
  label: string
  value: string | number
  icon?: string
  trend?: string
  trendUp?: boolean
  loading?: boolean
}

export default function StatCard({ label, value, icon, trend, trendUp, loading }: Props) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-2">
        {icon && <span className="text-2xl">{icon}</span>}
        {trend && (
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              trendUp
                ? 'bg-red-50 text-red-600'
                : 'bg-green-50 text-green-600'
            }`}
          >
            {trend}
          </span>
        )}
      </div>
      {loading ? (
        <div className="h-8 w-20 bg-gray-100 rounded animate-pulse mt-1" />
      ) : (
        <p className="text-2xl font-bold text-gray-900">{value}</p>
      )}
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  )
}
