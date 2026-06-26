import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

export function SitesList() {
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState('siteName')
  const [sortDir, setSortDir] = useState(1)
  const qc = useQueryClient()
  const navigate = useNavigate()

  const { data: sites = [], isLoading } = useQuery({ queryKey: ['sites'], queryFn: api.sites })
  const { data: gateways = [] } = useQuery({ queryKey: ['gateways'], queryFn: api.gateways })

  // Build gateway count per site
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
    <div className="p-6 max-w-6xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-100">Sites</h1>
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
              {sites.length === 0 ? 'No sites cached yet. Run a sync from the dashboard.' : 'No results.'}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
