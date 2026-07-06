import AlertBanner from './AlertBanner.jsx'
import WeaknessRadar from './WeaknessRadar.jsx'
import GrowthTrend from './GrowthTrend.jsx'
import ErrorDonut from './ErrorDonut.jsx'
import { computeAlert, computeErrorBreakdown, computeMockTrend, computePatternStats } from '../lib/analytics.js'

export default function Dashboard({ mocks }) {
  const patternStats = computePatternStats(mocks)
  const mockTrend = computeMockTrend(mocks)
  const errorBreakdown = computeErrorBreakdown(mocks)
  const alert = computeAlert(patternStats)

  return (
    <div className="flex flex-col gap-4">
      <AlertBanner alert={alert} />
      <WeaknessRadar data={patternStats} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GrowthTrend data={mockTrend} />
        <ErrorDonut data={errorBreakdown} />
      </div>
    </div>
  )
}
