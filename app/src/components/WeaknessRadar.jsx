import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CHART, barColor } from '../lib/colors.js'

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="rounded-lg border border-gray-100 bg-white/95 backdrop-blur-sm px-3 py-2 text-[11px] shadow-lg shadow-black/5">
      <div className="font-semibold text-gray-900">{d.pattern}</div>
      <div className="font-normal text-gray-400">{d.topic}</div>
      <div className="mt-1 font-medium tabular-nums text-gray-600">
        {d.accuracy}% accuracy · {d.correct}/{d.attempted} correct
      </div>
    </div>
  )
}

export default function WeaknessRadar({ data }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-5">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-[13px] font-semibold tracking-tight text-gray-900">Weakness Radar</div>
        <div className="text-[11px] font-normal text-gray-400">Accuracy % by Low-Level Pattern</div>
      </div>
      {data.length === 0 ? (
        <EmptyState text="Sync a mock to populate the weakness radar." />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 48 }}>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="4 4" vertical={false} />
            <XAxis
              dataKey="pattern"
              tick={{ fontSize: 10, fill: CHART.axis }}
              tickLine={false}
              axisLine={{ stroke: CHART.grid }}
              interval={0}
              angle={-35}
              textAnchor="end"
              height={70}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 10, fill: CHART.axis }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: '#00000006' }} />
            <Bar dataKey="accuracy" radius={[6, 6, 0, 0]} maxBarSize={28}>
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
    <div className="h-[200px] flex items-center justify-center text-[12px] font-normal text-gray-400 rounded-lg border border-dashed border-gray-200 bg-gray-50/50">
      {text}
    </div>
  )
}
