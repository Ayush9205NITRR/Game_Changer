import { IconCheck, IconWarning } from './icons.jsx'

export default function AlertBanner({ alert }) {
  if (alert.level === 'critical') {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-gray-800 bg-gray-900 px-4 py-3.5 shadow-sm">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-red-500/15">
          <IconWarning className="h-4 w-4 text-red-400" />
        </span>
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-widest text-red-400">Urgent Alert</div>
          <div className="text-[13px] font-medium text-gray-100 mt-0.5">{alert.message}</div>
        </div>
      </div>
    )
  }

  if (alert.level === 'watch') {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3.5 shadow-sm">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-100">
          <IconWarning className="h-4 w-4 text-amber-600" />
        </span>
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-widest text-amber-600">Watch</div>
          <div className="text-[13px] font-medium text-amber-800 mt-0.5">{alert.message}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3.5 shadow-sm">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-100">
        <IconCheck className="h-4 w-4 text-gray-400" />
      </span>
      <div className="text-[13px] font-medium text-gray-500">{alert.message}</div>
    </div>
  )
}
