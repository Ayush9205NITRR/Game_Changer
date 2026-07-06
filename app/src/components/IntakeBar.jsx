import { useRef, useState } from 'react'
import { downloadMasterSchema, parseMockCsv } from '../lib/csv.js'

export default function IntakeBar({ onRowsParsed }) {
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  async function handleFile(file) {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Only .csv files are accepted.')
      return
    }
    setError('')
    setBusy(true)
    try {
      const rows = await parseMockCsv(file)
      if (rows.length === 0) {
        setError('No rows found in that file.')
      } else {
        onRowsParsed(rows, file.name)
      }
    } catch (e) {
      setError('Could not parse that CSV.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="border border-[var(--border)] bg-[var(--card)]">
      <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--border)]">
        <div>
          <div className="text-[13px] font-semibold tracking-tight">Intake</div>
          <div className="text-[11px] text-[var(--t2)]">Download the schema, fill it in, upload it back.</div>
        </div>
        <button
          onClick={downloadMasterSchema}
          className="text-[12px] font-medium px-3 py-1.5 border border-[var(--border2)] hover:border-[var(--text)] hover:bg-[var(--text)] hover:text-white transition-colors"
        >
          Download Master Schema
        </button>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          handleFile(e.dataTransfer.files?.[0])
        }}
        onClick={() => inputRef.current?.click()}
        className={`m-5 mt-4 flex flex-col items-center justify-center gap-1 border border-dashed py-8 cursor-pointer transition-colors ${
          dragging ? 'border-[var(--text)] bg-[var(--bg)]' : 'border-[var(--border2)] hover:bg-[var(--bg)]'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
        <div className="text-[12px] font-medium">
          {busy ? 'Parsing…' : 'Drop filled mock CSV here, or click to browse'}
        </div>
        <div className="text-[11px] text-[var(--t3)]">.csv only — mapped rows appear below for review</div>
        {error && <div className="text-[11px] text-[var(--red)] mt-1">{error}</div>}
      </div>
    </div>
  )
}
