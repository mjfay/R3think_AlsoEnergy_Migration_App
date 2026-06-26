// UI labels use "Extraction" — internal code calls these "migrations" for legacy compatibility
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { api, getBase } from '../lib/api'

const STATUS_STYLES = {
  pending:   'bg-zinc-700 text-zinc-300',
  running:   'bg-blue-900/60 text-blue-300',
  done:      'bg-emerald-900/60 text-emerald-300',
  error:     'bg-red-900/60 text-red-300',
  cancelled: 'bg-zinc-700 text-zinc-400',
  emailed:   'bg-purple-900/60 text-purple-300',
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
}

function DownloadButton({ job }) {
  const navigate = useNavigate()

  async function handleDownload(e) {
    e.preventDefault()
    e.stopPropagation()
    const safeName = (job.name || 'extraction').replace(/[^a-z0-9_\-]/gi, '_')
    const dateStr = new Date().toISOString().slice(0, 10)
    const suggestedName = `${safeName}_${dateStr}.csv`

    try {
      if (window.__TAURI__) {
        const { save } = await import('@tauri-apps/plugin-dialog')
        const { writeTextFile } = await import('@tauri-apps/plugin-fs')
        const dest = await save({
          defaultPath: suggestedName,
          filters: [{ name: 'CSV files', extensions: ['csv'] }],
        })
        if (!dest) return
        const res = await fetch(`${getBase()}/jobs/${job.id}/csv`)
        if (!res.ok) throw new Error(`${res.status}`)
        const text = await res.text()
        await writeTextFile(dest, text)
      } else {
        const res = await fetch(`${getBase()}/jobs/${job.id}/csv`)
        if (!res.ok) throw new Error(`${res.status}`)
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = suggestedName; a.click()
        URL.revokeObjectURL(url)
      }
    } catch (e) {
      alert(`Download failed: ${e.message}`)
    }
  }

  return (
    <button
      onClick={handleDownload}
      className="text-xs px-2.5 py-1 border border-zinc-700 text-zinc-400 hover:text-emerald-300 hover:border-emerald-700 rounded transition-colors whitespace-nowrap"
      title="Download CSV"
    >
      Download CSV
    </button>
  )
}

export function MigrationsList() {
  const qc = useQueryClient()
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => api.get('/jobs'),
    refetchInterval: 5000,
  })

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Extractions</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Each extraction syncs a set of sites and produces a CSV for N3uron migration.
          </p>
        </div>
        <Link
          to="/migrations/new"
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          + New Extraction
        </Link>
      </div>

      {isLoading && (
        <div className="text-sm text-zinc-500">Loading…</div>
      )}

      {!isLoading && jobs.length === 0 && (
        <div className="border border-zinc-700 rounded-xl p-12 text-center">
          <p className="text-zinc-400 mb-4">No extractions yet.</p>
          <Link
            to="/migrations/new"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Start your first extraction
          </Link>
        </div>
      )}

      {jobs.length > 0 && (
        <div className="border border-zinc-700 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700 bg-zinc-800/50">
                <th className="text-left px-4 py-3 text-zinc-400 font-medium">Name</th>
                <th className="text-left px-4 py-3 text-zinc-400 font-medium">Sites</th>
                <th className="text-left px-4 py-3 text-zinc-400 font-medium">Devices</th>
                <th className="text-left px-4 py-3 text-zinc-400 font-medium">Status</th>
                <th className="text-left px-4 py-3 text-zinc-400 font-medium">Created</th>
                <th className="text-right px-4 py-3 text-zinc-400 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job, i) => (
                <tr
                  key={job.id}
                  className={`border-b border-zinc-800 hover:bg-zinc-800/30 transition-colors ${
                    i === jobs.length - 1 ? 'border-b-0' : ''
                  }`}
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/migrations/${job.id}`}
                      className="text-zinc-100 hover:text-blue-400 font-medium transition-colors"
                    >
                      {job.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-zinc-400">{job.siteIds.length}</td>
                  <td className="px-4 py-3 text-zinc-400">
                    {job.devicesFound > 0 ? job.devicesFound : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[job.status] || STATUS_STYLES.pending}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-zinc-400">{fmtDate(job.createdAt)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      {(job.status === 'done' || job.status === 'emailed') && (
                        <DownloadButton job={job} />
                      )}
                      <Link
                        to={`/migrations/${job.id}`}
                        className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
                      >
                        View →
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
