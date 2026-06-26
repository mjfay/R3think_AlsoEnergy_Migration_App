import { useState } from 'react'

export function JsonViewer({ data, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-zinc-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 bg-zinc-800/60 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
      >
        <span className="font-mono">Raw JSON</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <pre className="p-4 text-xs font-mono text-zinc-300 bg-zinc-900 overflow-auto max-h-96 leading-relaxed">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  )
}
