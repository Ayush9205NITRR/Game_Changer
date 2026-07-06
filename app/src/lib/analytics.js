const ALERT_THRESHOLD = 60
const MIN_ATTEMPTS_FOR_SIGNAL = 2

export function flattenRows(mocks) {
  return mocks.flatMap((m) => m.rows.map((r) => ({ ...r, mockId: m.id, mockName: m.name })))
}

export function computePatternStats(mocks) {
  const rows = flattenRows(mocks)
  const byPattern = new Map()
  for (const r of rows) {
    if (!r.pattern || r.status === 'Skipped' || !r.status) continue
    const key = r.pattern
    if (!byPattern.has(key)) byPattern.set(key, { pattern: key, topic: r.topic, correct: 0, attempted: 0 })
    const bucket = byPattern.get(key)
    bucket.attempted += 1
    if (r.status === 'Correct') bucket.correct += 1
  }
  return Array.from(byPattern.values())
    .map((b) => ({ ...b, accuracy: Math.round((b.correct / b.attempted) * 1000) / 10 }))
    .sort((a, b) => a.accuracy - b.accuracy)
}

export function computeMockTrend(mocks) {
  return mocks.map((m) => {
    const attempted = m.rows.filter((r) => r.status === 'Correct' || r.status === 'Incorrect').length
    const correct = m.rows.filter((r) => r.status === 'Correct').length
    const accuracy = attempted ? Math.round((correct / attempted) * 1000) / 10 : 0
    return { label: m.name, date: m.date, accuracy, correct, attempted }
  })
}

export function computeErrorBreakdown(mocks) {
  const rows = flattenRows(mocks)
  const counts = {}
  for (const r of rows) {
    if (r.status !== 'Incorrect') continue
    const key = r.errorType || 'Unspecified'
    counts[key] = (counts[key] || 0) + 1
  }
  return Object.entries(counts).map(([name, value]) => ({ name, value }))
}

export function computeAlert(patternStats) {
  const signal = patternStats.filter((p) => p.attempted >= MIN_ATTEMPTS_FOR_SIGNAL)
  if (signal.length === 0) {
    return { level: 'neutral', message: 'Awaiting sufficient data. Sync at least one mock to activate the diagnostic engine.' }
  }
  const worst = signal[0]
  if (worst.accuracy < ALERT_THRESHOLD) {
    return {
      level: 'critical',
      message: `Urgent Alert: Accuracy in "${worst.pattern}" has dropped to ${worst.accuracy}% (below ${ALERT_THRESHOLD}%). Review simplification notes before next mock.`,
    }
  }
  if (worst.accuracy < 75) {
    return {
      level: 'watch',
      message: `Watch: "${worst.pattern}" is trending soft at ${worst.accuracy}% accuracy. Reinforce before it becomes a leak.`,
    }
  }
  return { level: 'clear', message: 'No critical leaks detected. All tracked patterns are holding above threshold.' }
}
