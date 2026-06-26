import { useEffect, useRef, useState } from 'react'
import { getBase } from '../lib/api'

export function SyncProgressDrawer({ open, onClose, onDone, limit = 0, syncUrl = null }) {
  const [events, setEvents] = useState([])
  const [done, setDone] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const bottomRef = useRef(null)

  useEffect(() => {
    if (!open) return
    setEvents([])
    setDone(false)
    setProgress({ current: 0, total: 0 })

    const url = syncUrl || (limit > 0
      ? `${getBase()}/sync/all?limit=${limit}`
      : `${getBase()}/sync/all`)
    const es = new EventSource(url)
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data)
      setEvents(prev => [...prev, ev])

      if (ev.type === 'sites_loaded') {
        setProgress({ current: 0, total: ev.total })
      } else if (ev.type === 'site_done' || ev.type === 'site_error') {
        setProgress({ current: ev.index, total: ev.total })
      } else if (ev.type === 'done' || ev.type === 'error') {
        setDone(true)
        es.close()
        onDone?.()
      }
    }
    es.onerror = () => {
      setEvents(prev => [...prev, { type: 'error', error: 'SSE connection lost — is the backend running?' }])
      setDone('error')
      es.close()
    }
    return () => es.close()
  }, [open])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  if (!open) return null

  const pct = progress.total ? Math.round((progress.current / progress.total) * 100) : 0

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={done ? onClose : undefined} />
      <div className="relative w-full max-w-lg bg-zinc-900 border-l border-zinc-700 flex flex-col h-full shadow-2xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-700">
          <span className="font-semibold text-zinc-100">Sync All Sites</span>
          {done && (
            <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200 text-xl leading-none">×</button>
          )}
        </div>

        {progress.total > 0 && (
          <div className="px-4 py-3 border-b border-zinc-700/50">
            <div className="flex justify-between text-xs text-zinc-400 mb-1">
              <span>{progress.current} / {progress.total} sites</span>
              <span>{pct}%</span>
            </div>
            <div className="h-1.5 bg-zinc-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-4 space-y-1 font-mono text-xs">
          {events.map((ev, i) => (
            <EventLine key={i} ev={ev} />
          ))}
          <div ref={bottomRef} />
        </div>

        {done === true && (
          <div className="px-4 py-3 border-t border-zinc-700 text-center text-sm text-green-400">
            Sync complete
          </div>
        )}
        {done === 'error' && (
          <div className="px-4 py-3 border-t border-zinc-700 text-center text-sm text-red-400">
            Sync failed — check that the backend started correctly
          </div>
        )}
      </div>
    </div>
  )
}

function EventLine({ ev }) {
  if (ev.type === 'sites_loaded')
    return <div className="text-zinc-400">Loaded {ev.total} sites, fetching hardware…</div>
  if (ev.type === 'site_done')
    return (
      <div className="text-zinc-300">
        <span className="text-zinc-500">[{ev.index}/{ev.total}]</span>{' '}
        <span className="text-blue-400">{ev.siteName}</span>{' '}
        <span className="text-zinc-500">— {ev.deviceCount} device{ev.deviceCount !== 1 ? 's' : ''}</span>
      </div>
    )
  if (ev.type === 'site_error')
    return (
      <div className="text-red-400">
        <span className="text-zinc-500">[{ev.index}/{ev.total}]</span>{' '}
        {ev.siteName}: {ev.error}
      </div>
    )
  if (ev.type === 'done')
    return <div className="text-green-400 mt-2">✓ All done</div>
  if (ev.type === 'error')
    return <div className="text-red-400">Error: {ev.error}</div>
  return null
}
