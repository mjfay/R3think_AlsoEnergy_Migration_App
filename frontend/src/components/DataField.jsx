export function DataField({ label, value, mono = false }) {
  if (value == null || value === '') return null
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-zinc-500 uppercase tracking-wider">{label}</span>
      <span className={`text-sm text-zinc-200 ${mono ? 'font-mono' : ''}`}>
        {String(value)}
      </span>
    </div>
  )
}
