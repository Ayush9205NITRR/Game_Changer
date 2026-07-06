import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { EmptyState } from './WeaknessRadar.jsx'

const COLORS = {
  Conceptual: '#B91C1C',
  Calculation: '#B45309',
  Misread: '#65655F',
  'Silly Mistake': '#A5A59E',
  Unspecified: '#CCCBC5',
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0]
  return (
    <div className="border border-[var(--border2)] bg-[var(--card)] px-3 py-2 text-[11px]">
      <span className="font-semibold">{d.name}</span> · {d.value} error{d.value === 1 ? '' : 's'}
    </div>
  )
}

export default function ErrorDonut({ data }) {
  const total = data.reduce((s, d) => s + d.value, 0)
  return (
    <div className="border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-[13px] font-semibold tracking-tight">Error Root-Cause</div>
        <div className="text-[11px] text-[var(--t2)]">{total} incorrect answers analyzed</div>
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
              paddingAngle={2}
              stroke="none"
            >
              {data.map((d) => (
                <Cell key={d.name} fill={COLORS[d.name] || '#CCCBC5'} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend
              layout="vertical"
              align="right"
              verticalAlign="middle"
              iconType="square"
              iconSize={8}
              wrapperStyle={{ fontSize: 11, color: '#65655F' }}
            />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
