import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, getBase } from '../lib/api'
import { StatusBadge } from '../components/StatusBadge'
import { SyncProgressDrawer } from '../components/SyncProgressDrawer'
import { SiteSyncPicker } from '../components/SiteSyncPicker'

const STATUS_STYLES = {
  pending:   'bg-zinc-700 text-zinc-300',
  running:   'bg-blue-900/60 text-blue-300',
  done:      'bg-emerald-900/60 text-emerald-300',
  error:     'bg-red-900/60 text-red-300',
  cancelled: 'bg-zinc-700 text-zinc-400',
  emailed:   'bg-purple-900/60 text-purple-300',
}

function tokenColor(status) {
  if (status === 'valid') return 'green'
  if (status === 'expired') return 'yellow'
  return 'gray'
}

function fmtDate(iso, opts) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, opts)
}

function StatCard({ label, value, small = false }) {
  return (
    <div className="border border-zinc-700 rounded-lg p-4 bg-zinc-800/30">
      <div className="text-xs text-zinc-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`font-semibold text-zinc-100 ${small ? 'text-sm' : 'text-2xl'}`}>{value}</div>
    </div>
  )
}

// ─── Sites section ──────────────────────────────────────────────────────────

function SitesSection() {
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState('siteName')
  const [sortDir, setSortDir] = useState(1)
  const qc = useQueryClient()
  const navigate = useNavigate()

  const { data: sites = [], isLoading } = useQuery({ queryKey: ['sites'], queryFn: api.sites })
  const { data: gateways = [] } = useQuery({ queryKey: ['gateways'], queryFn: api.gateways })

  const gwCountBySite = gateways.reduce((acc, gw) => {
    acc[gw.siteId] = (acc[gw.siteId] ?? 0) + 1
    return acc
  }, {})

  const resync = useMutation({
    mutationFn: (id) => api.syncSite(id),
    onSuccess: () => qc.invalidateQueries(),
  })

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => -d)
    else { setSortKey(key); setSortDir(1) }
  }

  const filtered = sites
    .filter(s => s.siteName.toLowerCase().includes(search.toLowerCase()) || String(s.siteId).includes(search))
    .sort((a, b) => {
      const av = a[sortKey] ?? ''
      const bv = b[sortKey] ?? ''
      return typeof av === 'number' ? (av - bv) * sortDir : String(av).localeCompare(String(bv)) * sortDir
    })

  const SortHeader = ({ label, k }) => (
    <th
      onClick={() => toggleSort(k)}
      className="px-3 py-2 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider cursor-pointer hover:text-zinc-200 select-none whitespace-nowrap"
    >
      {label} {sortKey === k ? (sortDir === 1 ? '↑' : '↓') : ''}
    </th>
  )

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">Sites</h2>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search sites…"
          className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-blue-500 w-64"
        />
      </div>

      {isLoading ? (
        <div className="text-zinc-500 text-sm">Loading…</div>
      ) : (
        <div className="border border-zinc-700 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-zinc-800/60 border-b border-zinc-700">
              <tr>
                <SortHeader label="Site Name" k="siteName" />
                <SortHeader label="Site ID" k="siteId" />
                <SortHeader label="Devices" k="deviceCount" />
                <th className="px-3 py-2 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Gateways</th>
                <SortHeader label="Timezone" k="timezone" />
                <SortHeader label="Last Synced" k="lastSynced" />
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {filtered.map(site => (
                <tr
                  key={site.siteId}
                  onClick={() => navigate(`/sites/${site.siteId}`)}
                  className="hover:bg-zinc-800/50 cursor-pointer transition-colors"
                >
                  <td className="px-3 py-2.5 text-sm text-zinc-200">{site.siteName}</td>
                  <td className="px-3 py-2.5 text-xs font-mono text-zinc-400">{site.siteId}</td>
                  <td className="px-3 py-2.5 text-sm text-zinc-300">{site.deviceCount}</td>
                  <td className="px-3 py-2.5 text-sm text-zinc-400">{gwCountBySite[site.siteId] ?? '—'}</td>
                  <td className="px-3 py-2.5 text-xs text-zinc-400">{site.timezone ?? '—'}</td>
                  <td className="px-3 py-2.5 text-xs text-zinc-500">{fmtDate(site.lastSynced)}</td>
                  <td className="px-3 py-2.5">
                    <button
                      onClick={e => { e.stopPropagation(); resync.mutate(site.siteId) }}
                      disabled={resync.isPending}
                      className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-40"
                    >
                      Re-sync
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div className="px-4 py-6 text-center text-sm text-zinc-500">
              {sites.length === 0 ? 'No sites cached yet. Use "Select Sites…" above to sync.' : 'No results.'}
            </div>
          )}
        </div>
      )}
    </section>
  )
}

// ─── Exports section ────────────────────────────────────────────────────────

function ExportDownloadButton({ job }) {
  async function handleDownload(e) {
    e.preventDefault()
    e.stopPropagation()
    const safeName = (job.name || 'export').replace(/[^a-z0-9_\-]/gi, '_')
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
        const res = await fetch(`${getBase()}/jobs/${job.id}/csv`, { credentials: 'include' })
        if (!res.ok) throw new Error(`${res.status}`)
        const text = await res.text()
        await writeTextFile(dest, text)
      } else {
        const res = await fetch(`${getBase()}/jobs/${job.id}/csv`, { credentials: 'include' })
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

function ExportsSection() {
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => api.get('/jobs'),
    refetchInterval: 5000,
  })

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">Exports</h2>
        <Link
          to="/export"
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded-lg transition-colors"
        >
          + New Export
        </Link>
      </div>

      {isLoading && <div className="text-sm text-zinc-500">Loading…</div>}

      {!isLoading && jobs.length === 0 && (
        <div className="border border-zinc-700 rounded-xl p-8 text-center">
          <p className="text-zinc-400 mb-3 text-sm">No exports yet.</p>
          <Link
            to="/export"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Start your first export
          </Link>
        </div>
      )}

      {jobs.length > 0 && (
        <div className="border border-zinc-700 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700 bg-zinc-800/50">
                <th className="text-left px-4 py-2.5 text-zinc-400 font-medium text-xs uppercase tracking-wider">Name</th>
                <th className="text-left px-4 py-2.5 text-zinc-400 font-medium text-xs uppercase tracking-wider">Sites</th>
                <th className="text-left px-4 py-2.5 text-zinc-400 font-medium text-xs uppercase tracking-wider">Status</th>
                <th className="text-left px-4 py-2.5 text-zinc-400 font-medium text-xs uppercase tracking-wider">Created</th>
                <th className="text-right px-4 py-2.5 text-zinc-400 font-medium text-xs uppercase tracking-wider">Actions</th>
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
                  <td className="px-4 py-2.5">
                    <Link
                      to={`/export/${job.id}`}
                      className="text-zinc-100 hover:text-blue-400 font-medium transition-colors"
                    >
                      {job.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-zinc-400">{job.siteIds.length}</td>
                  <td className="px-4 py-2.5">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[job.status] || STATUS_STYLES.pending}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-zinc-400">{fmtDate(job.createdAt, { dateStyle: 'short', timeStyle: 'short' })}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center justify-end gap-2">
                      {(job.status === 'done' || job.status === 'emailed') && (
                        <ExportDownloadButton job={job} />
                      )}
                      <Link
                        to={`/export/${job.id}`}
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
    </section>
  )
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export function Dashboard() {
  const [pickerOpen, setPickerOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [syncUrl, setSyncUrl] = useState(null)
  const qc = useQueryClient()

  const { data: health } = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 30000 })
  const { data: stats } = useQuery({ queryKey: ['stats'], queryFn: api.stats })

  const tokenStatus = health?.token?.status ?? 'unknown'

  function handleStartSync(url) {
    setSyncUrl(url)
    setPickerOpen(false)
    setDrawerOpen(true)
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-100">Dashboard</h1>
        <StatusBadge
          label={tokenStatus === 'valid' ? `Token valid (${health.token.expires_in_seconds}s)` : tokenStatus}
          color={tokenColor(tokenStatus)}
        />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Sites cached" value={stats?.totalSites ?? '—'} />
        <StatCard label="Devices cached" value={stats?.totalDevices ?? '—'} />
        <StatCard label="Last sync" value={fmtDate(stats?.lastSynced)} small />
      </div>

      {/* Sync action */}
      <div className="border border-zinc-700 rounded-lg p-5 bg-zinc-800/30">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium text-zinc-200">Sync Sites</div>
            <div className="text-xs text-zinc-500 mt-0.5">
              Choose which sites to pull hardware data from
            </div>
          </div>
          <button
            onClick={() => setPickerOpen(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Select Sites…
          </button>
        </div>
      </div>

      <SitesSection />
      <ExportsSection />

      <SiteSyncPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onStartSync={handleStartSync}
      />

      <SyncProgressDrawer
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setSyncUrl(null) }}
        onDone={() => { qc.invalidateQueries(); qc.invalidateQueries(['ae-sites']) }}
        syncUrl={syncUrl}
      />
    </div>
  )
}
