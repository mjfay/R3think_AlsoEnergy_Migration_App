const colors = {
  green:  'bg-green-900/50 text-green-300 border border-green-700/50',
  yellow: 'bg-yellow-900/50 text-yellow-300 border border-yellow-700/50',
  red:    'bg-red-900/50 text-red-300 border border-red-700/50',
  gray:   'bg-zinc-800 text-zinc-400 border border-zinc-700',
  blue:   'bg-blue-900/50 text-blue-300 border border-blue-700/50',
}

export function StatusBadge({ label, color = 'gray' }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${colors[color]}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${color === 'green' ? 'bg-green-400' : color === 'yellow' ? 'bg-yellow-400' : color === 'red' ? 'bg-red-400' : color === 'blue' ? 'bg-blue-400' : 'bg-zinc-500'}`} />
      {label}
    </span>
  )
}
