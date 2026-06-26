import { useState, useMemo, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, getBase } from '../lib/api'

/**
 * Modal that lets users pick specific AlsoEnergy sites to sync.
 * Fetches the live site list from AlsoEnergy (not the local cache).
 */
export function SiteSyncPicker({ open, onClose, onStartSync }) {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState(new Set())

  // Live site list from AlsoEnergy (not cached DB)
  const { data: sites = [], isLoading, error } = useQuery({
    queryKey: ['ae-sites'],
    queryFn: () => api.get('/ae/sites'),
    enabled: open,
    staleTime: 5 * 60 * 1000,
  })

  // Also load cached sites to show device counts + last-synced
  const { data: cachedSites = [] } = useQuery({
    queryKey: ['sites'],
    queryFn: api.sites,
    enabled: open,
    staleTime: 30_000,
  })

  const cachedById = useMemo(() => {
    const m = {}
    for (const s of cachedSites) m[s.siteId] = s
    return m
  }, [cachedSites])

  // Reset selection when picker opens
  useEffect(() => {
    if (open) { setSearch(''); setSelected(new Set()) }
  }, [open])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return sites
    return sites.filter(s =>
      s.siteName.toLowerCase().includes(q) ||
      String(s.siteId).includes(q) ||
      (s.city || '').toLowerCase().includes(q) ||
      (s.state || '').toLowerCase().includes(q)
    )
  }, [sites, search])

  function toggleSite(id) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function selectAllFiltered() {
    setSelected(prev => {
      const next = new Set(prev)
      filtered.forEach(s => next.add(s.siteId))
      return next
    })
  }

  function deselectAllFiltered() {
    setSelected(prev => {
      const next = new Set(prev)
      filtered.forEach(s => next.delete(s.siteId))
      return next
    })
  }

  function handleSync() {
    if (selected.size === 0) return
    const ids = [...selected].join(',')
    const url = `${getBase()}/sync/all?site_ids=${ids}`
    onStartSync(url)
  }

  if (!open) return null

  const allFilteredSelected = filtered.length > 0 && filtered.every(s => selected.has(s.siteId))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl flex flex-col max-h-[85vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-700">
          <div>
            <h2 className="text-base font-semibold text-zinc-100">Select Sites to Sync</h2>
            <p className="text-xs text-zinc-500 mt-0.5">Choose which AlsoEnergy sites to pull hardware data from.</p>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300 text-xl leading-none ml-4">×</button>
        </div>

        {/* Search bar */}
        <div className="px-5 py-3 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
              </svg>
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search sites by name, ID, or location…"
                className="w-full pl-9 pr-3 py-2 rounded-lg border border-zinc-600 bg-zinc-800 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              onClick={allFilteredSelected ? deselectAllFiltered : selectAllFiltered}
              className="text-xs text-blue-400 hover:text-blue-300 whitespace-nowrap transition-colors"
            >
              {allFilteredSelected ? 'Deselect all' : 'Select all'}
            </button>
          </div>
          <div className="flex items-center justify-between mt-2">
            <span className="text-xs text-zinc-500">
              {isLoading ? 'Loading sites…' : `Showing ${filtered.length} of ${sites.length} sites`}
            </span>
            {selected.size > 0 && (
              <span className="text-xs font-medium text-blue-400">{selected.size} selected</span>
            )}
          </div>
        </div>

        {/* Site list */}
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center p-12 gap-3">
              <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-zinc-400">Fetching site list from AlsoEnergy…</span>
            </div>
          )}

          {error && (
            <div className="p-6 text-center">
              <p className="text-sm text-red-400">Failed to load sites — is the backend running and authenticated?</p>
            </div>
          )}

          {!isLoading && !error && filtered.length === 0 && (
            <div className="p-8 text-center text-sm text-zinc-500">No sites match your search.</div>
          )}

          {!isLoading && !error && filtered.length > 0 && (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-zinc-900 border-b border-zinc-800">
                <tr>
                  <th className="w-10 px-4 py-2" />
                  <th className="text-left px-3 py-2 text-xs font-medium text-zinc-400 uppercase tracking-wider">Site Name</th>
                  <th className="text-left px-3 py-2 text-xs font-medium text-zinc-400 uppercase tracking-wider">ID</th>
                  <th className="text-left px-3 py-2 text-xs font-medium text-zinc-400 uppercase tracking-wider">Location</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-zinc-400 uppercase tracking-wider">Cached</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((site, i) => {
                  const cached = cachedById[site.siteId]
                  const isSelected = selected.has(site.siteId)
                  return (
                    <tr
                      key={site.siteId}
                      onClick={() => toggleSite(site.siteId)}
                      className={`cursor-pointer border-b border-zinc-800 transition-colors ${
                        isSelected ? 'bg-blue-900/20 hover:bg-blue-900/30' : 'hover:bg-zinc-800/50'
                      } ${i === filtered.length - 1 ? 'border-b-0' : ''}`}
                    >
                      <td className="px-4 py-2.5 w-10">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSite(site.siteId)}
                          onClick={e => e.stopPropagation()}
                          className="w-4 h-4 rounded accent-blue-500"
                        />
                      </td>
                      <td className="px-3 py-2.5 text-zinc-200 font-medium">{site.siteName}</td>
                      <td className="px-3 py-2.5 text-xs font-mono text-zinc-500">{site.siteId}</td>
                      <td className="px-3 py-2.5 text-xs text-zinc-400">
                        {[site.city, site.state].filter(Boolean).join(', ') || '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right text-xs text-zinc-500">
                        {cached
                          ? <span className="text-emerald-500">{cached.deviceCount ?? 0} devices</span>
                          : <span className="text-zinc-700">—</span>
                        }
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-zinc-700 flex items-center justify-between">
          <span className="text-sm text-zinc-400">
            {selected.size === 0
              ? 'No sites selected'
              : `${selected.size} site${selected.size === 1 ? '' : 's'} selected`}
          </span>
          <div className="flex gap-3">
            <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200 border border-zinc-600 rounded-lg transition-colors">
              Cancel
            </button>
            <button
              onClick={handleSync}
              disabled={selected.size === 0}
              className="px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
            >
              Sync {selected.size > 0 ? `${selected.size} Site${selected.size === 1 ? '' : 's'}` : 'Selected Sites'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
