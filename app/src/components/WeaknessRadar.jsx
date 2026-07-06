import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
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

function PatternTick({ x, y, payload }) {
  const label = payload.value.length > 24 ? `${payload.value.slice(0, 22)}…` : payload.value
  return (
    <text x={x} y={y} dy={4} textAnchor="end" fontSize={11} fontWeight={500} fill="#374151">
      {label}
    </text>
  )
}

export default function WeaknessRadar({ data }) {
  const rowHeight = 36
  const chartHeight = Math.max(180, data.length * rowHeight + 32)

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-5">
      <div className="flex items-baseline justify-between mb-4">
        <div className="text-[13px] font-semibold tracking-tight text-gray-900">Weakness Radar</div>
        <div className="flex items-center gap-3 text-[11px] font-normal text-gray-400">
          <span>Accuracy % by Low-Level Pattern</span>
          <span className="flex items-center gap-1.5">
            <svg width="12" height="2" className="shrink-0">
              <line x1="0" y1="1" x2="12" y2="1" stroke="#B0B4BB" strokeWidth="1.5" strokeDasharray="3 2" />
            </svg>
            60% threshold
          </span>
        </div>
      </div>
      {data.length === 0 ? (
        <EmptyState text="Sync a mock to populate the weakness radar." />
      ) : (
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 32, left: 8, bottom: 4 }}
            barCategoryGap="28%"
          >
            <CartesianGrid stroke={CHART.grid} strokeDasharray="4 4" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, 100]}
              tick={{ fontSize: 10, fill: CHART.axis }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            <YAxis
              type="category"
              dataKey="pattern"
              width={148}
              tick={<PatternTick />}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: '#00000005' }} />
            <Bar
              dataKey="accuracy"
              radius={[0, 6, 6, 0]}
              maxBarSize={16}
              background={{ fill: '#F3F4F6', radius: 6 }}
              label={{ position: 'right', formatter: (v) => `${v}%`, fill: '#374151', fontSize: 11, fontWeight: 600 }}
              isAnimationActive={false}
            >
              {data.map((d) => (
                <Cell key={d.pattern} fill={barColor(d.accuracy)} />
              ))}
            </Bar>
            <ReferenceLine x={60} stroke="#B0B4BB" strokeDasharray="3 3" />
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
