import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

function barColor(accuracy) {
  if (accuracy < 60) return '#B91C1C'
  if (accuracy < 80) return '#B45309'
  return '#15803D'
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="border border-[var(--border2)] bg-[var(--card)] px-3 py-2 text-[11px]">
      <div className="font-semibold">{d.pattern}</div>
      <div className="text-[var(--t2)]">{d.topic}</div>
      <div className="mt-1 tabular-nums">
        {d.accuracy}% accuracy · {d.correct}/{d.attempted} correct
      </div>
    </div>
  )
}

export default function WeaknessRadar({ data }) {
  return (
    <div className="border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-[13px] font-semibold tracking-tight">Weakness Radar</div>
        <div className="text-[11px] text-[var(--t2)]">Accuracy % by Low-Level Pattern</div>
      </div>
      {data.length === 0 ? (
        <EmptyState text="Sync a mock to populate the weakness radar." />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 48 }}>
            <CartesianGrid stroke="#E2E1DC" vertical={false} />
            <XAxis
              dataKey="pattern"
              tick={{ fontSize: 10, fill: '#65655F' }}
              interval={0}
              angle={-35}
              textAnchor="end"
              height={70}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 10, fill: '#65655F' }}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: '#F5F4F0' }} />
            <Bar dataKey="accuracy" radius={[2, 2, 0, 0]} maxBarSize={36}>
              {data.map((d) => (
                <Cell key={d.pattern} fill={barColor(d.accuracy)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

export function EmptyState({ text }) {
  return (
    <div className="h-[200px] flex items-center justify-center text-[12px] text-[var(--t3)] border border-dashed border-[var(--border2)]">
      {text}
    </div>
  )
}
