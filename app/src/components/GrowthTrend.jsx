import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { EmptyState } from './WeaknessRadar.jsx'
import { CHART } from '../lib/colors.js'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="rounded-lg border border-gray-100 bg-white/95 backdrop-blur-sm px-3 py-2 text-[11px] shadow-lg shadow-black/5">
      <div className="font-semibold text-gray-900">{label}</div>
      <div className="font-medium tabular-nums text-gray-600">
        {d.accuracy}% accuracy · {d.correct}/{d.attempted} correct
      </div>
    </div>
  )
}

export default function GrowthTrend({ data }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-5">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-[13px] font-semibold tracking-tight text-gray-900">Growth Trend</div>
        <div className="text-[11px] font-normal text-gray-400">Accuracy % by Mock</div>
      </div>
      {data.length === 0 ? (
        <EmptyState text="Sync mocks over time to trace your ROI curve." />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 4, right: 16, left: -16, bottom: 4 }}>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="4 4" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: CHART.axis }} tickLine={false} axisLine={{ stroke: CHART.grid }} />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 10, fill: CHART.axis }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: CHART.grid, strokeWidth: 1 }} />
            <Line
              type="monotone"
              dataKey="accuracy"
              stroke={CHART.accent}
              strokeWidth={2.5}
              dot={{ r: 3.5, fill: '#fff', stroke: CHART.accent, strokeWidth: 2 }}
              activeDot={{ r: 5.5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
