import { useRef, useState } from 'react'
import { downloadMasterSchema, parseMockCsv } from '../lib/csv.js'
import { IconDownload, IconUpload } from './icons.jsx'

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
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <div>
          <div className="text-[13px] font-semibold tracking-tight text-gray-900">Intake</div>
          <div className="text-[12px] font-normal text-gray-500">Download the schema, fill it in, upload it back.</div>
        </div>
        <button
          onClick={downloadMasterSchema}
          className="inline-flex items-center gap-1.5 text-[12px] font-medium px-3.5 py-2 rounded-lg border border-gray-200 text-gray-700 shadow-sm hover:border-gray-300 hover:bg-gray-50 transition-colors duration-150"
        >
          <IconDownload className="h-3.5 w-3.5 text-gray-400" />
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
        className={`m-6 mt-4 flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed py-10 cursor-pointer transition-colors duration-150 ${
          dragging ? 'border-indigo-400 bg-indigo-50/40' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50/60'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
        <div className={`flex items-center justify-center h-9 w-9 rounded-full ${dragging ? 'bg-indigo-100' : 'bg-gray-100'} transition-colors duration-150`}>
          <IconUpload className={`h-4 w-4 ${dragging ? 'text-indigo-500' : 'text-gray-400'}`} />
        </div>
        <div className="text-[12px] font-medium text-gray-700">
          {busy ? 'Parsing…' : 'Drop filled mock CSV here, or click to browse'}
        </div>
        <div className="text-[11px] font-normal text-gray-400">.csv only — mapped rows appear below for review</div>
        {error && <div className="text-[11px] font-medium text-red-500 mt-1">{error}</div>}
      </div>
    </div>
  )
}
