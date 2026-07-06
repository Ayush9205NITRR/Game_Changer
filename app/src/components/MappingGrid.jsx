import { useMemo } from 'react'
import { SCHEMA, TOPICS, STATUSES, ERROR_TYPES, blankRow } from '../schema.js'
import { IconTrash } from './icons.jsx'

function Cell({ children, className = '' }) {
  return <td className={`border-b border-gray-100 px-2.5 py-1.5 align-middle ${className}`}>{children}</td>
}

const selectCls =
  'w-full bg-white border border-gray-200 rounded-md px-2 py-1.5 text-[12px] text-gray-700 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-gray-900/5 focus:border-gray-400 disabled:opacity-30 disabled:cursor-not-allowed'

const STATUS_STYLE = {
  Correct: { active: 'bg-white text-emerald-600 shadow-sm', label: 'Corr' },
  Incorrect: { active: 'bg-white text-red-500 shadow-sm', label: 'Inco' },
  Skipped: { active: 'bg-white text-gray-500 shadow-sm', label: 'Skip' },
}

export default function MappingGrid({ rows, onChange, onSync, onDiscard, mockName, mockDate, onMetaChange }) {
  const incompleteCount = useMemo(
    () => rows.filter((r) => !r.topic || !r.pattern || !r.status).length,
    [rows],
  )

  function updateRow(id, patch) {
    onChange(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)))
  }

  function deleteRow(id) {
    onChange(rows.filter((r) => r.id !== id))
  }

  function addRow() {
    const nextQno = rows.length ? Math.max(...rows.map((r) => Number(r.qno) || 0)) + 1 : 1
    onChange([...rows, blankRow(nextQno)])
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-b border-gray-100">
        <div>
          <div className="text-[13px] font-semibold tracking-tight text-gray-900">Diagnostic Core</div>
          <div className="text-[12px] font-normal text-gray-500">
            {rows.length} rows pending review
            {incompleteCount > 0 && <span className="text-amber-600 font-medium"> · {incompleteCount} need mapping</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={mockName}
            onChange={(e) => onMetaChange({ name: e.target.value })}
            placeholder="Mock label"
            className="text-[12px] text-gray-700 px-2.5 py-1.5 rounded-md border border-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-900/5 focus:border-gray-400 transition-colors duration-150 w-32"
          />
          <input
            type="date"
            value={mockDate}
            onChange={(e) => onMetaChange({ date: e.target.value })}
            className="text-[12px] text-gray-700 px-2.5 py-1.5 rounded-md border border-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-900/5 focus:border-gray-400 transition-colors duration-150"
          />
          <button
            onClick={onDiscard}
            className="text-[12px] font-medium px-3.5 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-colors duration-150"
          >
            Discard
          </button>
          <button
            disabled={incompleteCount > 0 || rows.length === 0}
            onClick={onSync}
            className="text-[12px] font-semibold px-3.5 py-1.5 rounded-lg bg-gray-900 text-white shadow-sm hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors duration-150"
          >
            {incompleteCount > 0 ? `Sync to Engine (${incompleteCount} incomplete)` : 'Sync to Engine'}
          </button>
        </div>
      </div>

      <div className="overflow-x-auto max-h-[520px]">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-white/95 backdrop-blur-sm z-10">
            <tr className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
              <th className="border-b border-gray-200 px-2.5 py-2.5 w-14">Q.No.</th>
              <th className="border-b border-gray-200 px-2.5 py-2.5 w-40">High-Level Topic</th>
              <th className="border-b border-gray-200 px-2.5 py-2.5 w-56">Low-Level Pattern</th>
              <th className="border-b border-gray-200 px-2.5 py-2.5 w-52">Status</th>
              <th className="border-b border-gray-200 px-2.5 py-2.5 w-36">Error Type</th>
              <th className="border-b border-gray-200 px-2.5 py-2.5">Simplification Note</th>
              <th className="border-b border-gray-200 px-2.5 py-2.5 w-8" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const isIncorrect = r.status === 'Incorrect'
              const isIncomplete = !r.topic || !r.pattern || !r.status
              const rowAccent = isIncorrect
                ? 'border-l-[3px] border-l-red-400 bg-red-50/40 hover:bg-red-50/70'
                : isIncomplete
                ? 'border-l-[3px] border-l-amber-300 bg-amber-50/30 hover:bg-amber-50/60'
                : 'border-l-[3px] border-l-transparent hover:bg-gray-50'
              return (
                <tr key={r.id} className={`transition-colors duration-100 ${rowAccent}`}>
                  <Cell>
                    <input
                      type="text"
                      value={r.qno}
                      onChange={(e) => updateRow(r.id, { qno: e.target.value })}
                      className="w-full bg-transparent text-[12px] text-gray-700 tabular-nums focus:outline-none"
                    />
                  </Cell>
                  <Cell>
                    <select
                      className={selectCls}
                      value={r.topic}
                      onChange={(e) => updateRow(r.id, { topic: e.target.value, pattern: '' })}
                    >
                      <option value="">Select topic</option>
                      {TOPICS.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </Cell>
                  <Cell>
                    <select
                      className={selectCls}
                      value={r.pattern}
                      disabled={!r.topic}
                      onChange={(e) => updateRow(r.id, { pattern: e.target.value })}
                    >
                      <option value="">{r.topic ? 'Select pattern' : '—'}</option>
                      {(SCHEMA[r.topic] || []).map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </Cell>
                  <Cell>
                    <div className="inline-flex w-full items-center gap-0.5 rounded-full bg-gray-100 p-0.5">
                      {STATUSES.map((s) => {
                        const active = r.status === s
                        return (
                          <button
                            key={s}
                            onClick={() =>
                              updateRow(r.id, { status: s, errorType: s === 'Incorrect' ? r.errorType : '' })
                            }
                            className={`flex-1 text-[10px] font-semibold uppercase tracking-wide py-1 rounded-full transition-all duration-150 ${
                              active ? STATUS_STYLE[s].active : 'text-gray-400 hover:text-gray-600'
                            }`}
                          >
                            {STATUS_STYLE[s].label}
                          </button>
                        )
                      })}
                    </div>
                  </Cell>
                  <Cell>
                    <select
                      className={selectCls}
                      value={r.errorType}
                      disabled={!isIncorrect}
                      onChange={(e) => updateRow(r.id, { errorType: e.target.value })}
                    >
                      <option value="">{isIncorrect ? 'Select cause' : '—'}</option>
                      {ERROR_TYPES.map((e) => (
                        <option key={e} value={e}>
                          {e}
                        </option>
                      ))}
                    </select>
                  </Cell>
                  <Cell>
                    <input
                      type="text"
                      value={r.note}
                      onChange={(e) => updateRow(r.id, { note: e.target.value })}
                      placeholder="1-sentence translation rule…"
                      className="w-full bg-transparent border border-transparent rounded-md px-2 py-1.5 text-[12px] font-normal text-gray-700 placeholder:text-gray-300 focus:outline-none focus:bg-white focus:border-gray-200 focus:ring-2 focus:ring-gray-900/5 transition-colors duration-150"
                    />
                  </Cell>
                  <Cell className="text-center">
                    <button
                      onClick={() => deleteRow(r.id)}
                      className="inline-flex items-center justify-center h-6 w-6 rounded-md text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors duration-150"
                      aria-label="Delete row"
                    >
                      <IconTrash className="h-3.5 w-3.5" />
                    </button>
                  </Cell>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="px-6 py-3 border-t border-gray-100">
        <button onClick={addRow} className="text-[11px] font-medium text-gray-400 hover:text-gray-700 transition-colors duration-150">
          + Add Row
        </button>
      </div>
    </div>
  )
}
