// Desaturated chart palette — avoids pure traffic-light red/green.
export const CHART = {
  danger: '#D97757',
  warning: '#D9A441',
  success: '#4C9A7A',
  accent: '#4F46E5',
  grid: '#E5E7EB',
  axis: '#9CA3AF',
}

export const ERROR_COLORS = {
  Conceptual: '#D97757',
  Calculation: '#D9A441',
  Misread: '#9CA3AF',
  'Silly Mistake': '#D1D5DB',
  Unspecified: '#E5E7EB',
}

export function barColor(accuracy) {
  if (accuracy < 60) return CHART.danger
  if (accuracy < 80) return CHART.warning
  return CHART.success
}
