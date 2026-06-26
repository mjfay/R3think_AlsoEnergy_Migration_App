import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { StatusBadge } from '../components/StatusBadge'
import { CopyButton } from '../components/CopyButton'
import { JsonViewer } from '../components/JsonViewer'

const FLAG_COLORS = { IsEnabled: 'green', IsOffline: 'yellow', OutOfService: 'red' }

export function GatewayDetail() {
  const { gatewayId } = useParams()
  const navigate = useNavigate()

  const { data: gw, isLoading, error } = useQuery({
    queryKey: ['gateway', gatewayId],
    queryFn: () => api.gateway(gatewayId),
  })

  if (isLoading) return <div className="p-6 text-zinc-500 text-sm">Loading…</div>
  if (error) return <div className="p-6 text-red-400 text-sm">{error.message}</div>

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">

      {/* Header */}
      <div>
        <button
          onClick={() => gw.siteId ? navigate(`/sites/${gw.siteId}`) : navigate('/sites')}
          className="text-xs text-zinc-500 hover:text-zinc-300 mb-2 block"
        >
          ← {gw.siteId ? `Site ${gw.siteId}` : 'Sites'}
        </button>
        <h1 className="text-xl font-semibold text-zinc-100">{gw.name}</h1>
        <div className="text-xs font-mono text-zinc-500 mt-0.5 flex items-center gap-1">
          {gw.gatewayId}
          <CopyButton value={gw.gatewayId} />
        </div>
        {gw.siteId && (
          <div className="text-xs text-zinc-500 mt-1">
            Site:{' '}
            <Link to={`/sites/${gw.siteId}`} className="text-blue-400 hover:text-blue-300">
              {gw.siteId}
            </Link>
          </div>
        )}
      </div>

      {/* Parameters */}
      {gw.parameters?.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-zinc-500 uppercase tracking-wider border-b border-zinc-800 pb-1">
            Gateway Parameters
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="py-1.5 text-left text-zinc-500 font-medium w-1/3">Key</th>
                <th className="py-1.5 text-left text-zinc-500 font-medium">Value</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {gw.parameters.map(({ key, value }) => (
                <tr key={key}>
                  <td className="py-1.5 font-mono text-zinc-400 pr-4">{key}</td>
                  <td className="py-1.5 font-mono text-zinc-200 flex items-center gap-1">
                    {value}
                    <CopyButton value={value} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Devices behind this gateway */}
      <div className="space-y-2">
        <div className="text-xs font-medium text-zinc-500 uppercase tracking-wider border-b border-zinc-800 pb-1">
          Devices ({gw.devices?.length ?? 0})
        </div>
        {gw.devices?.length > 0 ? (
          <div className="border border-zinc-700 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-zinc-800/60 border-b border-zinc-700">
                <tr>
                  {['Name', 'Func', 'Device Type', 'IP Address', 'Modbus ID', 'Flags'].map(h => (
                    <th key={h} className="px-3 py-2 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {gw.devices.map(hw => (
                  <tr
                    key={hw.id}
                    onClick={() => navigate(`/sites/${hw.siteId}/hardware/${hw.id}`)}
                    className="hover:bg-zinc-800/50 cursor-pointer transition-colors"
                  >
                    <td className="px-3 py-2.5 text-sm text-zinc-200 whitespace-nowrap">{hw.name}</td>
                    <td className="px-3 py-2.5 text-xs font-mono text-zinc-400">{hw.functionCode ?? '—'}</td>
                    <td className="px-3 py-2.5 text-xs text-zinc-400">{hw.deviceType ?? '—'}</td>
                    <td className="px-3 py-2.5 text-xs font-mono text-zinc-400">{hw.ipAddress ?? '—'}</td>
                    <td className="px-3 py-2.5 text-xs font-mono text-zinc-400">
                      {hw.modbusAddress && hw.modbusAddress !== '0' ? hw.modbusAddress : '—'}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {hw.flags?.map(f => <StatusBadge key={f} label={f} color={FLAG_COLORS[f] ?? 'gray'} />)}
                        {hw.isVirtualDevice && <StatusBadge label="Virtual" color="gray" />}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-zinc-500">No devices associated with this gateway in cache.</div>
        )}
      </div>

      {/* Raw device configs from gateway endpoint */}
      <JsonViewer data={gw.deviceConfigs} />
    </div>
  )
}
