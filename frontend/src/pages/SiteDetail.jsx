import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { DataField } from '../components/DataField'
import { JsonViewer } from '../components/JsonViewer'
import { StatusBadge } from '../components/StatusBadge'

const FLAG_COLORS = { IsEnabled: 'green', IsOffline: 'yellow', OutOfService: 'red' }
const flagColor = f => FLAG_COLORS[f] ?? 'gray'

function groupByGateway(hardware) {
  const groups = new Map()
  for (const hw of hardware) {
    const key = hw.gatewayId ?? '__none__'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(hw)
  }
  return groups
}

export function SiteDetail() {
  const { siteId } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState('overview')
  const [groupByGw, setGroupByGw] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['site', siteId],
    queryFn: () => api.site(siteId),
  })

  if (isLoading) return <div className="p-6 text-zinc-500 text-sm">Loading…</div>
  if (error) return <div className="p-6 text-red-400 text-sm">{error.message}</div>

  const { site, hardware } = data

  const HwRow = ({ hw }) => {
    const virtual = hw.isVirtualDevice
    const display = (val, fallback = '—') => virtual ? '—' : (val ?? fallback)
    return (
      <tr
        onClick={() => navigate(`/sites/${siteId}/hardware/${hw.id}`)}
        className="hover:bg-zinc-800/50 cursor-pointer transition-colors"
      >
        <td className="px-3 py-2.5 text-xs text-zinc-500 w-6">
          {virtual && <span title="Virtual device" className="text-zinc-600">◈</span>}
        </td>
        <td className="px-3 py-2.5 text-sm text-zinc-200 whitespace-nowrap">{hw.name}</td>
        <td className="px-3 py-2.5 text-xs font-mono text-zinc-400">{hw.functionCode ?? '—'}</td>
        <td className="px-3 py-2.5 text-xs text-zinc-400">{hw.deviceType ?? '—'}</td>
        <td className="px-3 py-2.5 text-xs font-mono text-zinc-400">{hw.serialNumber ?? '—'}</td>
        <td className="px-3 py-2.5 text-xs font-mono text-zinc-400">{hw.ipAddress || ''}</td>
        <td className="px-3 py-2.5 text-xs font-mono text-zinc-400">{display(hw.modbusAddress !== '0' ? hw.modbusAddress : null)}</td>
        <td className="px-3 py-2.5 text-xs font-mono text-zinc-400 max-w-32">
          {hw.gatewayId ? (
            <Link
              to={`/gateways/${encodeURIComponent(hw.gatewayId)}`}
              onClick={e => e.stopPropagation()}
              title={hw.gatewayId}
              className="text-blue-400 hover:text-blue-300 truncate block max-w-28"
            >
              {hw.gatewayId}
            </Link>
          ) : '—'}
        </td>
        <td className="px-3 py-2.5">
          <div className="flex flex-wrap gap-1">
            {hw.flags.map(f => <StatusBadge key={f} label={f} color={flagColor(f)} />)}
          </div>
        </td>
      </tr>
    )
  }

  const GwGroupHeader = ({ gatewayId }) => (
    <tr className="bg-zinc-800/80">
      <td colSpan={9} className="px-3 py-1.5">
        {gatewayId === '__none__' ? (
          <span className="text-xs text-zinc-500 italic">No gateway</span>
        ) : (
          <Link
            to={`/gateways/${encodeURIComponent(gatewayId)}`}
            className="text-xs font-mono text-blue-400 hover:text-blue-300"
          >
            Gateway: {gatewayId}
          </Link>
        )}
      </td>
    </tr>
  )

  const tableHeaders = ['', 'Name', 'Func', 'Device Type', 'Serial', 'IP Address', 'Modbus ID', 'Gateway', 'Flags']

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      {/* Header */}
      <div>
        <button onClick={() => navigate('/sites')} className="text-xs text-zinc-500 hover:text-zinc-300 mb-2 block">← Sites</button>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-zinc-100">{site.siteName}</h1>
            <div className="text-xs font-mono text-zinc-500 mt-0.5">ID: {site.siteId}</div>
          </div>
          <a
            href={api.exportSite(siteId)}
            download={`site-${siteId}.json`}
            className="px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 text-zinc-200 rounded-lg transition-colors whitespace-nowrap"
          >
            Export JSON
          </a>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-zinc-700">
        {['overview', 'devices', 'raw'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm capitalize transition-colors border-b-2 -mb-px ${
              tab === t ? 'border-blue-500 text-zinc-100' : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {t === 'raw' ? 'Raw JSON' : t}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <DataField label="Address" value={[site.address, site.city, site.state, site.zipCode].filter(Boolean).join(', ')} />
          <DataField label="Country" value={site.country} />
          <DataField label="Timezone" value={site.timezone} />
          <DataField label="Customer ID" value={site.customerId} mono />
          <DataField label="Install Date" value={site.installDate} />
          <DataField label="Turn-On Date" value={site.turnOnDate} />
          <DataField label="System Size" value={site.systemSizeKw != null ? `${site.systemSizeKw} kW` : null} />
          <DataField label="Latitude" value={site.lat} mono />
          <DataField label="Longitude" value={site.lng} mono />
        </div>
      )}

      {tab === 'devices' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-zinc-500">{hardware.length} device{hardware.length !== 1 ? 's' : ''}</span>
            <button
              onClick={() => setGroupByGw(g => !g)}
              className={`text-xs px-2.5 py-1 rounded border transition-colors ${
                groupByGw
                  ? 'border-blue-600 text-blue-400 bg-blue-900/20'
                  : 'border-zinc-700 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Group by Gateway
            </button>
          </div>
          <div className="border border-zinc-700 rounded-lg overflow-hidden overflow-x-auto">
            <table className="w-full min-w-max">
              <thead className="bg-zinc-800/60 border-b border-zinc-700">
                <tr>
                  {tableHeaders.map(h => (
                    <th key={h} className="px-3 py-2 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {groupByGw
                  ? Array.from(groupByGateway(hardware).entries()).map(([gwId, rows]) => (
                      <>
                        <GwGroupHeader key={`hdr-${gwId}`} gatewayId={gwId} />
                        {rows.map(hw => <HwRow key={hw.id} hw={hw} />)}
                      </>
                    ))
                  : hardware.map(hw => <HwRow key={hw.id} hw={hw} />)
                }
              </tbody>
            </table>
            {hardware.length === 0 && (
              <div className="px-4 py-6 text-center text-sm text-zinc-500">No devices cached for this site.</div>
            )}
          </div>
        </div>
      )}

      {tab === 'raw' && (
        <div className="space-y-3">
          <JsonViewer data={site} defaultOpen />
          <div className="text-xs text-zinc-500 px-1">Hardware ({hardware.length} devices)</div>
          {hardware.map(hw => <JsonViewer key={hw.id} data={hw.rawJson} />)}
        </div>
      )}
    </div>
  )
}
