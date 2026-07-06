import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { EmptyState } from './WeaknessRadar.jsx'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="border border-[var(--border2)] bg-[var(--card)] px-3 py-2 text-[11px]">
      <div className="font-semibold">{label}</div>
      <div className="tabular-nums">
        {d.accuracy}% accuracy · {d.correct}/{d.attempted} correct
      </div>
    </div>
  )
}

export default function GrowthTrend({ data }) {
  return (
    <div className="border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-[13px] font-semibold tracking-tight">Growth Trend</div>
        <div className="text-[11px] text-[var(--t2)]">Accuracy % by Mock</div>
      </div>
      {data.length === 0 ? (
        <EmptyState text="Sync mocks over time to trace your ROI curve." />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 4, right: 16, left: -16, bottom: 4 }}>
            <CartesianGrid stroke="#E2E1DC" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#65655F' }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#65655F' }} tickFormatter={(v) => `${v}%`} />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="accuracy"
              stroke="#111110"
              strokeWidth={2}
              dot={{ r: 3, fill: '#111110' }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
