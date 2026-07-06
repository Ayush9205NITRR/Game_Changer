import Papa from 'papaparse'
import { SCHEMA, TOPICS, MASTER_SCHEMA_ROW_COUNT, blankRow } from '../schema.js'

const HEADERS = ['Q.No.', 'High-Level Topic', 'Low-Level Pattern', 'Status', 'Simplification Note']

export function buildMasterSchemaCsv() {
  const rows = [HEADERS]
  for (let i = 1; i <= MASTER_SCHEMA_ROW_COUNT; i++) {
    rows.push([i, '', '', '', ''])
  }
  const body = Papa.unparse(rows)
  const reference = [
    '',
    '# Valid Topic -> Pattern reference (do not upload this section)',
    ...TOPICS.flatMap((t) => [`# ${t}`, ...SCHEMA[t].map((p) => `#   - ${p}`)]),
  ].join('\n')
  return `${body}\n${reference}\n`
}

export function downloadMasterSchema() {
  const csv = buildMasterSchemaCsv()
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'master_schema_template.csv'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

const norm = (s) => String(s ?? '').trim().toLowerCase()

function matchTopic(raw) {
  const n = norm(raw)
  if (!n) return ''
  const hit = TOPICS.find((t) => norm(t) === n)
  return hit || ''
}

function matchPattern(topic, raw) {
  const n = norm(raw)
  if (!n || !topic || !SCHEMA[topic]) return ''
  const hit = SCHEMA[topic].find((p) => norm(p) === n)
  return hit || ''
}

function normalizeStatus(raw) {
  const n = norm(raw)
  if (['correct', 'right', 'c', '1', 'true'].includes(n)) return 'Correct'
  if (['incorrect', 'wrong', 'i', '0', 'false'].includes(n)) return 'Incorrect'
  if (['skipped', 'skip', 's', 'na', 'n/a'].includes(n)) return 'Skipped'
  return ''
}

function normalizeErrorType(raw) {
  const n = norm(raw)
  const map = {
    conceptual: 'Conceptual',
    calculation: 'Calculation',
    misread: 'Misread',
    'silly mistake': 'Silly Mistake',
    silly: 'Silly Mistake',
  }
  return map[n] || ''
}

function pick(row, ...keys) {
  for (const k of Object.keys(row)) {
    const nk = norm(k)
    if (keys.some((want) => nk === norm(want))) return row[k]
  }
  return ''
}

// Parses an uploaded mock CSV into editable grid rows, best-effort mapping
// free-text Topic/Pattern/Status values onto the fixed SCHEMA where possible.
export function parseMockCsv(file) {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        const rows = results.data
          .filter((r) => Object.values(r).some((v) => String(v ?? '').trim() !== ''))
          .map((r, idx) => {
            const qnoRaw = pick(r, 'Q.No.', 'Q.No', 'QNo', 'Question', 'Q')
            const topicRaw = pick(r, 'High-Level Topic', 'Topic')
            const patternRaw = pick(r, 'Low-Level Pattern', 'Pattern', 'Sub-Pattern')
            const statusRaw = pick(r, 'Status')
            const noteRaw = pick(r, 'Simplification Note', 'Note')
            const errorRaw = pick(r, 'Error Type', 'Error')

            const topic = matchTopic(topicRaw)
            const base = blankRow(qnoRaw || idx + 1)
            return {
              ...base,
              qno: qnoRaw || idx + 1,
              topic,
              pattern: matchPattern(topic, patternRaw),
              status: normalizeStatus(statusRaw),
              errorType: normalizeErrorType(errorRaw),
              note: noteRaw || '',
            }
          })
        resolve(rows)
      },
      error: reject,
    })
  })
}
