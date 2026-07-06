import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { EmptyState } from './WeaknessRadar.jsx'
import { ERROR_COLORS } from '../lib/colors.js'

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0]
  return (
    <div className="rounded-lg border border-gray-100 bg-white/95 backdrop-blur-sm px-3 py-2 text-[11px] shadow-lg shadow-black/5">
      <span className="font-semibold text-gray-900">{d.name}</span>{' '}
      <span className="font-medium text-gray-500">
        · {d.value} error{d.value === 1 ? '' : 's'}
      </span>
    </div>
  )
}

export default function ErrorDonut({ data }) {
  const total = data.reduce((s, d) => s + d.value, 0)
  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-5">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-[13px] font-semibold tracking-tight text-gray-900">Error Root-Cause</div>
        <div className="text-[11px] font-normal text-gray-400">{total} incorrect answers analyzed</div>
      </div>
      {data.length === 0 ? (
        <EmptyState text="Tag error types on incorrect rows to see the breakdown." />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={60}
              outerRadius={95}
              paddingAngle={3}
              cornerRadius={6}
              stroke="none"
            >
              {data.map((d) => (
                <Cell key={d.name} fill={ERROR_COLORS[d.name] || '#E5E7EB'} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend
              layout="vertical"
              align="right"
              verticalAlign="middle"
              iconType="circle"
              iconSize={7}
              wrapperStyle={{ fontSize: 11, fontWeight: 500, color: '#6B7280' }}
            />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
