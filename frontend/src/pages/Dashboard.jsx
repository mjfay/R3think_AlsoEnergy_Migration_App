import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { StatusBadge } from '../components/StatusBadge'
import { SyncProgressDrawer } from '../components/SyncProgressDrawer'
import { SiteSyncPicker } from '../components/SiteSyncPicker'

function tokenColor(status) {
  if (status === 'valid') return 'green'
  if (status === 'expired') return 'yellow'
  return 'gray'
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

export function Dashboard() {
  const [pickerOpen, setPickerOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [syncUrl, setSyncUrl] = useState(null)
  const qc = useQueryClient()

  const { data: health } = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 30000 })
  const { data: stats } = useQuery({ queryKey: ['stats'], queryFn: api.stats })
  const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: () => api.get('/jobs'), refetchInterval: 30000 })

  const tokenStatus = health?.token?.status ?? 'unknown'
  const readyJobs = jobs.filter(j => j.status === 'done' || j.status === 'emailed')

  function handleStartSync(url) {
    setSyncUrl(url)
    setPickerOpen(false)
    setDrawerOpen(true)
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-100">Dashboard</h1>
        <StatusBadge
          label={tokenStatus === 'valid' ? `Token valid (${health.token.expires_in_seconds}s)` : tokenStatus}
          color={tokenColor(tokenStatus)}
        />
      </div>

      {/* Ready-to-download banner */}
      {readyJobs.length > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-700 bg-emerald-900/10 px-4 py-3">
          <p className="text-sm text-emerald-300">
            {readyJobs.length === 1
              ? 'You have 1 extraction ready to download.'
              : `You have ${readyJobs.length} extractions ready to download.`}
          </p>
          <Link
            to="/migrations"
            className="text-xs px-3 py-1.5 border border-emerald-700 text-emerald-400 hover:text-emerald-200 hover:border-emerald-500 rounded-lg transition-colors whitespace-nowrap ml-4"
          >
            Go to Extractions →
          </Link>
        </div>
      )}

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
              Choose which AlsoEnergy sites to pull hardware data from
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

function StatCard({ label, value, small = false }) {
  return (
    <div className="border border-zinc-700 rounded-lg p-4 bg-zinc-800/30">
      <div className="text-xs text-zinc-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`font-semibold text-zinc-100 ${small ? 'text-sm' : 'text-2xl'}`}>{value}</div>
    </div>
  )
}
