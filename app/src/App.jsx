import { useEffect, useMemo, useState } from 'react'
import IntakeBar from './components/IntakeBar.jsx'
import MappingGrid from './components/MappingGrid.jsx'
import Dashboard from './components/Dashboard.jsx'
import { flattenRows } from './lib/analytics.js'

const STORAGE_KEY = 'game-changer.mocks.v1'

function loadMocks() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function App() {
  const [mocks, setMocks] = useState(loadMocks)
  const [pendingRows, setPendingRows] = useState([])
  const [mockMeta, setMockMeta] = useState({ name: '', date: todayIso() })
  const [notice, setNotice] = useState('')

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(mocks))
  }, [mocks])

  useEffect(() => {
    if (!notice) return
    const t = setTimeout(() => setNotice(''), 3200)
    return () => clearTimeout(t)
  }, [notice])

  const stats = useMemo(() => {
    const rows = flattenRows(mocks)
    const attempted = rows.filter((r) => r.status === 'Correct' || r.status === 'Incorrect').length
    const correct = rows.filter((r) => r.status === 'Correct').length
    const accuracy = attempted ? Math.round((correct / attempted) * 1000) / 10 : null
    return { mockCount: mocks.length, accuracy, leaks: rows.filter((r) => r.status === 'Incorrect').length }
  }, [mocks])

  function handleRowsParsed(rows, fileName) {
    setPendingRows(rows)
    setMockMeta({ name: fileName.replace(/\.csv$/i, '').slice(0, 24), date: todayIso() })
  }

  function handleSync() {
    const mockId = `mock-${Date.now()}`
    const name = mockMeta.name.trim() || `Mock ${mocks.length + 1}`
    setMocks([...mocks, { id: mockId, name, date: mockMeta.date, rows: pendingRows }])
    setPendingRows([])
    setMockMeta({ name: '', date: todayIso() })
    setNotice(`Synced "${name}" — ${pendingRows.length} rows locked into the engine.`)
  }

  function handleDiscard() {
    setPendingRows([])
    setMockMeta({ name: '', date: todayIso() })
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="sticky top-0 z-20 bg-white/90 backdrop-blur-sm border-b border-gray-200">
        <div className="max-w-[1200px] mx-auto px-6 py-3.5 flex items-center justify-between">
          <div>
            <div className="text-[14px] font-bold tracking-tight text-gray-900">GAME CHANGER</div>
            <div className="text-[10px] font-medium uppercase tracking-widest text-gray-400">Mock Diagnostic Engine</div>
          </div>
          <div className="flex items-center gap-2.5">
            <StatChip label="Mocks Synced" value={stats.mockCount} />
            <StatChip
              label="Overall Accuracy"
              value={stats.accuracy === null ? '—' : `${stats.accuracy}%`}
              tone={stats.accuracy !== null && stats.accuracy < 60 ? 'red' : undefined}
            />
            <StatChip label="Score Leaks" value={stats.leaks} tone={stats.leaks > 0 ? 'amber' : undefined} />
          </div>
        </div>
      </header>

      <main className="max-w-[1200px] mx-auto px-6 py-7 flex flex-col gap-5">
        <IntakeBar onRowsParsed={handleRowsParsed} />

        {pendingRows.length > 0 && (
          <MappingGrid
            rows={pendingRows}
            onChange={setPendingRows}
            onSync={handleSync}
            onDiscard={handleDiscard}
            mockName={mockMeta.name}
            mockDate={mockMeta.date}
            onMetaChange={(patch) => setMockMeta({ ...mockMeta, ...patch })}
          />
        )}

        <Dashboard mocks={mocks} />
      </main>

      {notice && (
        <div className="fixed bottom-5 right-5 flex items-center gap-2 bg-gray-900 text-white text-[12px] font-medium px-4 py-3 rounded-lg shadow-lg shadow-black/10 animate-[fadeIn_0.15s_ease-out]">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          {notice}
        </div>
      )}
    </div>
  )
}

function StatChip({ label, value, tone }) {
  const toneCls = tone === 'red' ? 'text-red-500' : tone === 'amber' ? 'text-amber-600' : 'text-gray-900'
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50 px-3.5 py-1.5 text-right transition-shadow hover:shadow-sm">
      <div className="text-[9px] font-medium uppercase tracking-widest text-gray-400">{label}</div>
      <div className={`text-[16px] font-bold tabular-nums leading-tight ${toneCls}`}>{value}</div>
    </div>
  )
}
