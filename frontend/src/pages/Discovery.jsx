import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, getBase } from '../lib/api'

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
}

function SortIcon({ col, sortCol, sortDir }) {
  if (col !== sortCol) return <span className="text-zinc-700 ml-1">↕</span>
  return <span className="text-blue-400 ml-1">{sortDir === 'desc' ? '↓' : '↑'}</span>
}

export function Discovery() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [scanning, setScanning] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0, siteName: '' })
  const [scanError, setScanError] = useState('')
  const [sortCol, setSortCol] = useState('tcpCount')
  const [sortDir, setSortDir] = useState('desc')
  const esRef = useRef(null)

  const { data: results = [], isLoading } = useQuery({
    queryKey: ['discovery'],
    queryFn: () => api.get('/discovery/results'),
  })

  function startScan() {
    if (scanning) return
    setScanning(true)
    setScanError('')
    setProgress({ current: 0, total: 0, siteName: '' })

    const es = new EventSource(`${getBase()}/discovery/events`)
    esRef.current = es

    es.onmessage = (e) => {
      const ev = JSON.parse(e.data)
      if (ev.type === 'started') {
        setProgress(p => ({ ...p, total: ev.total }))
      } else if (ev.type === 'scanning') {
        setProgress({ current: ev.index, total: ev.total, siteName: ev.siteName })
      } else if (ev.type === 'done') {
        es.close()
        setScanning(false)
        qc.invalidateQueries(['discovery'])
      } else if (ev.type === 'error') {
        setScanError(ev.error)
        es.close()
        setScanning(false)
      }
    }

    es.onerror = () => {
      setScanError('Connection to backend lost — try again.')
      es.close()
      setScanning(false)
    }
  }

  useEffect(() => () => esRef.current?.close(), [])

  function toggleSort(col) {
    if (sortCol === col) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    } else {
      setSortCol(col)
      setSortDir('desc')
    }
  }

  const sorted = [...results].sort((a, b) => {
    const mul = sortDir === 'desc' ? -1 : 1
    if (sortCol === 'siteName') return mul * a.siteName.localeCompare(b.siteName)
    if (sortCol === 'siteId') return mul * (a.siteId - b.siteId)
    return mul * ((a[sortCol] ?? 0) - (b[sortCol] ?? 0))
  })

  const pct = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0
  const hasResults = results.length > 0
  const lastScanned = results[0]?.lastScanned

  const cols = [
    { key: 'siteName', label: 'Site Name' },
    { key: 'siteId', label: 'Site ID' },
    { key: 'tcpCount', label: 'TCP Devices' },
    { key: 'rtuCount', label: 'RTU Devices' },
    { key: 'unknownCount', label: 'Other' },
  ]

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">TCP Device Discovery</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Scans your AlsoEnergy portfolio and reports which sites contain Modbus TCP devices.
            Use this to pick sites for migration validation.
          </p>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          {hasResults && !scanning && (
            <button
              onClick={startScan}
              className="px-3 py-1.5 border border-zinc-600 text-zinc-300 hover:text-zinc-100 text-sm rounded-lg transition-colors"
            >
              Re-scan
            </button>
          )}
          {!scanning && (
            <button
              onClick={startScan}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {hasResults ? 'Scan All Sites' : 'Scan All Sites for TCP Devices'}
            </button>
          )}
        </div>
      </div>

      {/* Scan progress */}
      {scanning && (
        <div className="border border-zinc-700 rounded-xl bg-zinc-900 p-5 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
            <span className="text-sm text-zinc-200">
              {progress.total > 0
                ? `Scanning ${progress.current} / ${progress.total} sites…`
                : 'Loading site list…'}
            </span>
          </div>
          {progress.siteName && (
            <p className="text-xs text-zinc-500 pl-7 truncate">{progress.siteName}</p>
          )}
          {progress.total > 0 && (
            <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {scanError && (
        <div className="rounded-lg border border-red-700 bg-red-900/10 p-4 text-sm text-red-400">
          {scanError}
        </div>
      )}

      {/* Empty state */}
      {!scanning && !hasResults && !isLoading && (
        <div className="border border-zinc-700 rounded-xl bg-zinc-900/40 p-12 text-center">
          <p className="text-zinc-500 text-sm">No scan results yet.</p>
          <p className="text-zinc-600 text-xs mt-1">Click "Scan All Sites for TCP Devices" to get started.</p>
        </div>
      )}

      {/* Results table */}
      {hasResults && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-zinc-500">
              {results.length} sites{lastScanned && ` · last scanned ${fmtDate(lastScanned)}`}
            </span>
            <span className="text-xs text-zinc-600">
              {results.filter(r => r.tcpCount > 0).length} sites with TCP devices
            </span>
          </div>

          <div className="border border-zinc-700 rounded-xl overflow-hidden overflow-x-auto">
            <table className="w-full min-w-max">
              <thead className="bg-zinc-800/60 border-b border-zinc-700">
                <tr>
                  {cols.map(({ key, label }) => (
                    <th
                      key={key}
                      onClick={() => toggleSort(key)}
                      className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider whitespace-nowrap cursor-pointer hover:text-zinc-200 select-none"
                    >
                      {label}
                      <SortIcon col={key} sortCol={sortCol} sortDir={sortDir} />
                    </th>
                  ))}
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {sorted.map(row => (
                  <tr
                    key={row.siteId}
                    className={`hover:bg-zinc-800/40 transition-colors ${row.tcpCount === 0 ? 'opacity-50' : ''}`}
                  >
                    <td className="px-4 py-2.5 text-sm text-zinc-200 whitespace-nowrap">{row.siteName}</td>
                    <td className="px-4 py-2.5 text-xs font-mono text-zinc-500">{row.siteId}</td>
                    <td className="px-4 py-2.5">
                      {row.tcpCount > 0 ? (
                        <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-blue-300">
                          <span className="w-2 h-2 rounded-full bg-blue-500" />
                          {row.tcpCount}
                        </span>
                      ) : (
                        <span className="text-xs text-zinc-600">0</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-zinc-400">{row.rtuCount || '—'}</td>
                    <td className="px-4 py-2.5 text-xs text-zinc-600">{row.unknownCount || '—'}</td>
                    <td className="px-4 py-2.5">
                      <button
                        onClick={() => navigate(`/migrations/new?siteId=${row.siteId}&siteName=${encodeURIComponent(row.siteName)}`)}
                        className="text-xs px-2.5 py-1 border border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:border-zinc-500 rounded transition-colors whitespace-nowrap"
                      >
                        Start Migration Job
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
