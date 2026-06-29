import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, getBase } from '../lib/api'
import { revealInFinder } from '../lib/shell'  // used in Toast "Show in Finder"

// ─── Toast ────────────────────────────────────────────────────────────────────
function Toast({ toast, onDismiss }) {
  if (!toast) return null
  const isError = toast.status === 'error'
  const isDone = toast.status === 'done'
  const isPending = toast.status === 'pending'
  return (
    <div className={`fixed bottom-6 right-6 z-50 w-80 rounded-xl border shadow-2xl p-4 transition-all
      ${isError ? 'border-red-700 bg-red-950/90' : isDone ? 'border-emerald-700 bg-zinc-900/95' : 'border-zinc-700 bg-zinc-900/95'}`}
    >
      <div className="flex items-start gap-3">
        {isPending && <div className="mt-0.5 w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin shrink-0" />}
        {isDone && <span className="text-emerald-400 text-lg leading-none shrink-0">✓</span>}
        {isError && <span className="text-red-400 text-lg leading-none shrink-0">✗</span>}
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium ${isError ? 'text-red-300' : 'text-zinc-100'}`}>{toast.title}</p>
          {toast.subtitle && <p className="text-xs text-zinc-400 mt-0.5 truncate">{toast.subtitle}</p>}
          {isDone && toast.savedPath && (
            <div className="flex gap-3 mt-2">
              <button onClick={() => revealInFinder(toast.savedPath)} className="text-xs text-blue-400 hover:text-blue-300">Show in Finder</button>
            </div>
          )}
          {isError && toast.onRetry && (
            <button onClick={toast.onRetry} className="text-xs text-red-400 hover:text-red-300 mt-1">Retry</button>
          )}
        </div>
        <button onClick={onDismiss} className="text-zinc-500 hover:text-zinc-300 text-lg leading-none shrink-0">×</button>
      </div>
    </div>
  )
}

const STATUS_STYLES = {
  pending:   'bg-zinc-700 text-zinc-300',
  running:   'bg-blue-900/60 text-blue-300 animate-pulse',
  done:      'bg-emerald-900/60 text-emerald-300',
  error:     'bg-red-900/60 text-red-300',
  cancelled: 'bg-zinc-700 text-zinc-400',
  emailed:   'bg-purple-900/60 text-purple-300',
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function StatPill({ label, value }) {
  return (
    <div className="border border-zinc-700 rounded-lg px-4 py-3 text-center">
      <div className="text-xs text-zinc-500 uppercase tracking-wider mb-1">{label}</div>
      <div className="text-xl font-semibold text-zinc-100">{value ?? '—'}</div>
    </div>
  )
}

// Progress view shown while job is running
function RunningView({ job, logLines, onCancel, sitesProcessed }) {
  const logRef = useRef(null)
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logLines])

  const done = sitesProcessed
  const total = job.siteIds.length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-zinc-200 font-medium">Running… {done} / {total} sites</span>
        </div>
        <button
          onClick={onCancel}
          className="text-xs px-3 py-1.5 border border-zinc-600 text-zinc-400 hover:text-red-400 hover:border-red-600 rounded-lg transition-colors"
        >
          Cancel
        </button>
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 transition-all duration-500"
          style={{ width: total > 0 ? `${(done / total) * 100}%` : '0%' }}
        />
      </div>

      {/* Live log */}
      <div
        ref={logRef}
        className="border border-zinc-700 rounded-lg bg-zinc-950 p-3 h-64 overflow-y-auto font-mono text-xs text-zinc-400 space-y-0.5"
      >
        {logLines.map((line, i) => (
          <div key={i} className={line.type === 'error' ? 'text-red-400' : line.type === 'done' ? 'text-emerald-400' : ''}>
            {line.text}
          </div>
        ))}
        {logLines.length === 0 && <div className="text-zinc-600">Waiting for events…</div>}
      </div>
    </div>
  )
}

// Completion view
function CompletionView({ job, onDownload }) {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-emerald-700 bg-emerald-900/10 p-5 flex items-start gap-4">
        <div className="text-emerald-400 text-2xl">✓</div>
        <div>
          <p className="font-semibold text-emerald-300">Export complete</p>
          <p className="text-sm text-emerald-500 mt-0.5">CSV generated and ready to download.</p>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatPill label="Sites" value={job.sitesSynced} />
        <StatPill label="Devices" value={job.devicesFound} />
        <StatPill label="Registers" value={job.registersCaptured} />
        <StatPill label="Errors" value={job.errorCount} />
      </div>

      <p className="text-sm text-zinc-400">
        Your CSV is ready. Download it below, or find it later in the{' '}
        <a href="/migrations" className="text-blue-400 hover:text-blue-300">Exports</a> tab.
      </p>
      <div className="flex flex-wrap gap-3 items-center">
        <button
          onClick={onDownload}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          Download CSV
        </button>
      </div>
    </div>
  )
}

export function MigrationJobDetail() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [logLines, setLogLines] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [sitesProcessed, setSitesProcessed] = useState(0)
  const [toast, setToast] = useState(null)
  const toastTimerRef = useRef(null)
  const esRef = useRef(null)

  const { data: job, refetch } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.get(`/jobs/${jobId}`),
    refetchInterval: streaming ? false : 5000,
  })

  function showToast(t, autoDismissMs = 5000) {
    clearTimeout(toastTimerRef.current)
    setToast(t)
    if (autoDismissMs > 0) {
      toastTimerRef.current = setTimeout(() => setToast(null), autoDismissMs)
    }
  }

  async function handleDownload() {
    const safeName = (job.name || 'migration').replace(/[^a-z0-9_\-]/gi, '_')
    const dateStr = new Date().toISOString().slice(0, 10)
    const suggestedName = `${safeName}_${dateStr}.csv`
    showToast({ status: 'pending', title: 'Waiting for save location…' }, 0)
    try {
      let savedPath = null
      if (window.__TAURI__) {
        const { save } = await import('@tauri-apps/plugin-dialog')
        const { writeTextFile } = await import('@tauri-apps/plugin-fs')
        const dest = await save({
          defaultPath: suggestedName,
          filters: [{ name: 'CSV files', extensions: ['csv'] }],
        })
        if (!dest) { setToast(null); return }
        showToast({ status: 'pending', title: `Downloading ${dest.split('/').pop()}…`, subtitle: dest }, 0)
        const res = await fetch(`${getBase()}/jobs/${job.id}/csv`)
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
        const text = await res.text()
        await writeTextFile(dest, text)
        savedPath = dest
      } else {
        const res = await fetch(`${getBase()}/jobs/${job.id}/csv`)
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = suggestedName
        a.click()
        URL.revokeObjectURL(url)
      }
      showToast({
        status: 'done',
        title: `Downloaded ${suggestedName}`,
        subtitle: savedPath,
        savedPath,
      }, 8000)
    } catch (e) {
      showToast({
        status: 'error',
        title: 'Download failed',
        subtitle: e.message,
        onRetry: handleDownload,
      }, 0)
    }
  }

  function startJob() {
    if (streaming || !job) return
    setLogLines([])
    setStreaming(true)
    setSitesProcessed(0)

    const es = new EventSource(`${getBase()}/jobs/${jobId}/events`)
    esRef.current = es

    es.onmessage = (e) => {
      const event = JSON.parse(e.data)
      let text = ''

      if (event.type === 'started') text = `Starting sync for ${event.total} sites…`
      else if (event.type === 'site_start') text = `[${event.index}/${event.total}] Syncing ${event.siteName}…`
      else if (event.type === 'site_done') text = `[${event.index}/${event.total}] ✓ ${event.siteName} — ${event.deviceCount} devices`
      else if (event.type === 'site_error') text = `[${event.index}/${event.total}] ✗ ${event.siteName}: ${event.error}`
      else if (event.type === 'generating_csv') text = 'Generating CSV…'
      else if (event.type === 'done') text = `Done — ${event.sitesSynced} sites, ${event.devicesFound} devices, ${event.registersCaptured} registers`
      else if (event.type === 'cancelled') text = 'Job cancelled.'
      else if (event.type === 'error') text = `Error: ${event.error}`
      else text = JSON.stringify(event)

      setLogLines(prev => [...prev, { type: event.type, text }])

      if (event.type === 'site_done' || event.type === 'site_error') {
        setSitesProcessed(prev => prev + 1)
      }

      if (['done', 'error', 'cancelled'].includes(event.type)) {
        es.close()
        setStreaming(false)
        refetch()
        qc.invalidateQueries(['jobs'])
      }
    }

    es.onerror = () => {
      es.close()
      setStreaming(false)
      refetch()
    }
  }

  async function handleCancel() {
    try {
      await api.post(`/jobs/${jobId}/cancel`, {})
      // Give the backend a moment to process, then refetch
      setTimeout(() => { refetch(); qc.invalidateQueries(['jobs']) }, 800)
    } catch (e) {
      console.error('Cancel failed', e)
    }
  }

  async function handleForceReset() {
    // Used when job shows 'running' in DB but no SSE stream is active
    // (e.g. app was closed mid-run). Calls cancel which force-updates DB.
    try {
      await api.post(`/jobs/${jobId}/cancel`, {})
      setStreaming(false)
      setTimeout(() => { refetch(); qc.invalidateQueries(['jobs']) }, 500)
    } catch (e) {
      console.error('Force reset failed', e)
    }
  }

  // Auto-start if job is pending on first load
  useEffect(() => {
    if (job?.status === 'pending' && !streaming) {
      startJob()
    }
  }, [job?.status])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      esRef.current?.close()
      clearTimeout(toastTimerRef.current)
    }
  }, [])

  if (!job) {
    return <div className="p-6 text-zinc-500 text-sm">Loading…</div>
  }

  const isStreaming = streaming
  const isStuck = job.status === 'running' && !streaming  // DB says running but no local SSE
  const isRunning = job.status === 'running' || streaming
  const isDone = job.status === 'done' || job.status === 'emailed'
  const isError = job.status === 'error'
  const isCancelled = job.status === 'cancelled'

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link to="/migrations" className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors">
            ← Exports
          </Link>
          <h1 className="text-xl font-semibold text-zinc-100 mt-2">{job.name}</h1>
          <div className="flex items-center gap-3 mt-1">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[job.status] || STATUS_STYLES.pending}`}>
              {job.status}
            </span>
            <span className="text-xs text-zinc-500">{job.siteIds.length} sites</span>
            <span className="text-xs text-zinc-500">Created {fmtDate(job.createdAt)}</span>
          </div>
        </div>

        {/* Run button for pending/error/cancelled — not shown when stuck */}
        {(job.status === 'pending' || isError || isCancelled) && !streaming && !isStuck && (
          <button
            onClick={startJob}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {isError || isCancelled ? 'Re-run job' : 'Run job'}
          </button>
        )}
      </div>

      {/* Stuck: DB says running but no active stream (app was closed mid-run) */}
      {isStuck && (
        <div className="rounded-lg border border-amber-700 bg-amber-900/10 p-4 space-y-3">
          <div>
            <p className="text-sm font-medium text-amber-300">Job appears stuck</p>
            <p className="text-xs text-amber-500 mt-1">
              The app may have closed while this job was running. Click Cancel to reset it, then re-run.
            </p>
          </div>
          <button
            onClick={handleForceReset}
            className="text-xs px-3 py-1.5 border border-amber-700 text-amber-400 hover:text-amber-200 hover:border-amber-500 rounded-lg transition-colors"
          >
            Cancel stuck job
          </button>
        </div>
      )}

      {/* Running progress */}
      {isRunning && !isStuck && (
        <RunningView job={job} logLines={logLines} onCancel={handleCancel} sitesProcessed={sitesProcessed} />
      )}

      {/* Error state */}
      {isError && !streaming && (
        <div className="rounded-lg border border-red-700 bg-red-900/10 p-4">
          <p className="text-sm font-medium text-red-300">Job failed</p>
          {job.errorDetail && (
            <p className="text-xs text-red-400 mt-1 font-mono">{job.errorDetail}</p>
          )}
        </div>
      )}

      {/* Completed */}
      {isDone && !streaming && (
        <CompletionView job={job} onDownload={handleDownload} />
      )}

      {/* Cancelled */}
      {isCancelled && !streaming && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-800/40 p-4 text-sm text-zinc-400">
          Job was cancelled. Click <strong className="text-zinc-200">Re-run job</strong> to try again.
        </div>
      )}

      <Toast toast={toast} onDismiss={() => { clearTimeout(toastTimerRef.current); setToast(null) }} />
    </div>
  )
}
