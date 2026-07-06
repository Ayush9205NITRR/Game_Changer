import { useMemo, useState } from 'react'
import { SCHEMA, TOPICS, STATUSES, ERROR_TYPES, blankRow } from '../schema.js'

function Cell({ children, className = '' }) {
  return <td className={`border-b border-[var(--border)] px-2 py-1 align-middle ${className}`}>{children}</td>
}

const selectCls =
  'w-full bg-transparent border border-[var(--border2)] px-1.5 py-1 text-[12px] focus:outline-none focus:border-[var(--text)]'

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
    <div className="border border-[var(--border)] bg-[var(--card)]">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-b border-[var(--border)]">
        <div>
          <div className="text-[13px] font-semibold tracking-tight">Diagnostic Core</div>
          <div className="text-[11px] text-[var(--t2)]">
            {rows.length} rows pending review
            {incompleteCount > 0 && <span className="text-[var(--amber)]"> · {incompleteCount} need mapping</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={mockName}
            onChange={(e) => onMetaChange({ name: e.target.value })}
            placeholder="Mock label"
            className="text-[12px] px-2 py-1.5 border border-[var(--border2)] focus:outline-none focus:border-[var(--text)] w-32"
          />
          <input
            type="date"
            value={mockDate}
            onChange={(e) => onMetaChange({ date: e.target.value })}
            className="text-[12px] px-2 py-1.5 border border-[var(--border2)] focus:outline-none focus:border-[var(--text)]"
          />
          <button
            onClick={onDiscard}
            className="text-[12px] font-medium px-3 py-1.5 border border-[var(--border2)] hover:border-[var(--text)] transition-colors"
          >
            Discard
          </button>
          <button
            disabled={incompleteCount > 0 || rows.length === 0}
            onClick={onSync}
            className="text-[12px] font-semibold px-3 py-1.5 bg-[var(--text)] text-white disabled:opacity-30 disabled:cursor-not-allowed hover:opacity-85 transition-opacity"
          >
            {incompleteCount > 0 ? `Sync to Engine (${incompleteCount} incomplete)` : 'Sync to Engine'}
          </button>
        </div>
      </div>

      <div className="overflow-x-auto max-h-[520px]">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-[var(--card)] z-10">
            <tr className="text-[10px] uppercase tracking-wide text-[var(--t2)]">
              <th className="border-b border-[var(--border2)] px-2 py-2 w-14">Q.No.</th>
              <th className="border-b border-[var(--border2)] px-2 py-2 w-40">High-Level Topic</th>
              <th className="border-b border-[var(--border2)] px-2 py-2 w-56">Low-Level Pattern</th>
              <th className="border-b border-[var(--border2)] px-2 py-2 w-52">Status</th>
              <th className="border-b border-[var(--border2)] px-2 py-2 w-36">Error Type</th>
              <th className="border-b border-[var(--border2)] px-2 py-2">Simplification Note</th>
              <th className="border-b border-[var(--border2)] px-2 py-2 w-8" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const isIncorrect = r.status === 'Incorrect'
              const isIncomplete = !r.topic || !r.pattern || !r.status
              return (
                <tr
                  key={r.id}
                  className={
                    isIncorrect
                      ? 'bg-[var(--red-bg)]'
                      : isIncomplete
                      ? 'bg-[var(--amber-bg)]/40'
                      : 'hover:bg-[var(--bg)]'
                  }
                >
                  <Cell>
                    <input
                      type="text"
                      value={r.qno}
                      onChange={(e) => updateRow(r.id, { qno: e.target.value })}
                      className="w-full bg-transparent text-[12px] tabular-nums focus:outline-none"
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
                    <div className="flex gap-1">
                      {STATUSES.map((s) => (
                        <button
                          key={s}
                          onClick={() =>
                            updateRow(r.id, { status: s, errorType: s === 'Incorrect' ? r.errorType : '' })
                          }
                          className={`flex-1 text-[10px] font-semibold uppercase tracking-wide px-1.5 py-1 border transition-colors ${
                            r.status === s
                              ? s === 'Correct'
                                ? 'bg-[var(--green)] border-[var(--green)] text-white'
                                : s === 'Incorrect'
                                ? 'bg-[var(--red)] border-[var(--red)] text-white'
                                : 'bg-[var(--t2)] border-[var(--t2)] text-white'
                              : 'border-[var(--border2)] text-[var(--t2)] hover:border-[var(--text)]'
                          }`}
                        >
                          {s.slice(0, 4)}
                        </button>
                      ))}
                    </div>
                  </Cell>
                  <Cell>
                    <select
                      className={`${selectCls} disabled:opacity-30`}
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
                      className="w-full bg-transparent border border-transparent focus:border-[var(--border2)] px-1.5 py-1 text-[12px] focus:outline-none"
                    />
                  </Cell>
                  <Cell className="text-center">
                    <button
                      onClick={() => deleteRow(r.id)}
                      className="text-[var(--t3)] hover:text-[var(--red)] text-[13px] leading-none"
                      aria-label="Delete row"
                    >
                      ×
                    </button>
                  </Cell>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="px-5 py-2.5 border-t border-[var(--border)]">
        <button onClick={addRow} className="text-[11px] font-medium text-[var(--t2)] hover:text-[var(--text)]">
          + Add Row
        </button>
      </div>
    </div>
  )
}
