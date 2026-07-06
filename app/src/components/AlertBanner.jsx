const STYLES = {
  critical: 'border-[var(--red)] bg-[var(--red-bg)] text-[var(--red)]',
  watch: 'border-[var(--amber)] bg-[var(--amber-bg)] text-[var(--amber)]',
  clear: 'border-[var(--border2)] bg-[var(--card)] text-[var(--t2)]',
  neutral: 'border-[var(--border2)] bg-[var(--card)] text-[var(--t2)]',
}

const PREFIX = {
  critical: '🚨 ',
  watch: '⚠ ',
  clear: '✓ ',
  neutral: '· ',
}

export default function AlertBanner({ alert }) {
  return (
    <div className={`border px-4 py-3 text-[12px] font-medium tracking-tight ${STYLES[alert.level]}`}>
      {PREFIX[alert.level]}
      {alert.message}
    </div>
  )
}
