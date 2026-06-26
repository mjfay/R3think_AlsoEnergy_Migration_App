import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { DataField } from '../components/DataField'
import { CopyButton } from '../components/CopyButton'
import { JsonViewer } from '../components/JsonViewer'
import { StatusBadge } from '../components/StatusBadge'

const FLAG_COLORS = { IsEnabled: 'green', IsOffline: 'yellow', OutOfService: 'red' }
const SERIAL_COM_TYPES = ['Rs232', 'Rs485_2Wire', 'RS485_4Wire']
const NET_KEY_RE = /ip|host|address|remote/i

function comTypeBadgeColor(ct) {
  if (ct === 'Tcp') return 'blue'
  if (SERIAL_COM_TYPES.includes(ct)) return 'green'
  return 'gray'
}

function CopyField({ label, value, mono = true, highlight = false }) {
  if (value == null || value === '') return null
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-zinc-500 uppercase tracking-wider">{label}</span>
      <span className={`text-sm flex items-center gap-1 ${mono ? 'font-mono' : ''} ${highlight ? 'text-blue-300' : 'text-zinc-200'}`}>
        {String(value)}
        <CopyButton value={value} />
      </span>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="space-y-3">
      <div className="text-xs font-medium text-zinc-500 uppercase tracking-wider border-b border-zinc-800 pb-1">{title}</div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {children}
      </div>
    </div>
  )
}

function VirtualBanner() {
  return (
    <div className="flex items-start gap-3 px-4 py-3 rounded-lg bg-zinc-800/60 border border-zinc-700 text-sm text-zinc-400">
      <span className="mt-0.5 text-zinc-500">ⓘ</span>
      <span>
        <span className="text-zinc-300 font-medium">Virtual / aggregate device</span>
        {' — '}no direct Modbus configuration. This device represents rolled-up data from multiple physical devices and has no direct network connection.
      </span>
    </div>
  )
}

function ComTypeBadge({ comType, portMode }) {
  const display = portMode && portMode !== 'Unknown' ? portMode : comType
  if (!display || display === 'Unknown') return <StatusBadge label="Unknown" color="gray" />
  return <StatusBadge label={display} color={comTypeBadgeColor(display)} />
}

function DriverSettingsTable({ settings }) {
  const entries = Object.entries(settings)
  if (!entries.length) return <div className="text-xs text-zinc-500">No driver settings</div>
  return (
    <div className="col-span-full">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-zinc-800">
            <th className="py-1.5 text-left text-zinc-500 font-medium w-1/3">Key</th>
            <th className="py-1.5 text-left text-zinc-500 font-medium">Value</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/60">
          {entries.map(([k, v]) => {
            const highlight = NET_KEY_RE.test(k)
            return (
              <tr key={k}>
                <td className={`py-1.5 font-mono pr-4 ${highlight ? 'text-blue-400' : 'text-zinc-400'}`}>{k}</td>
                <td className="py-1.5 font-mono text-zinc-200 flex items-center gap-1">
                  {String(v)}
                  <CopyButton value={v} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function InverterTable({ inverters }) {
  if (!Array.isArray(inverters) || !inverters.length) return null
  const keys = ['ratedAcPower', 'stringCount', 'modulesPerString', 'wattsPerModule', 'azimuth', 'tilt', 'trackingMode']
  return (
    <div className="col-span-full overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-zinc-800">
            {keys.map(k => <th key={k} className="py-1.5 px-2 text-left text-zinc-500 font-medium whitespace-nowrap">{k}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/60">
          {inverters.map((inv, i) => (
            <tr key={i}>
              {keys.map(k => <td key={k} className="py-1.5 px-2 font-mono text-zinc-300">{inv[k] ?? '—'}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function DeviceDetail() {
  const { siteId, hardwareId } = useParams()
  const navigate = useNavigate()

  const { data: hw, isLoading, error } = useQuery({
    queryKey: ['hardware', siteId, hardwareId],
    queryFn: () => api.hardware(siteId, hardwareId),
  })

  if (isLoading) return <div className="p-6 text-zinc-500 text-sm">Loading…</div>
  if (error) return <div className="p-6 text-red-400 text-sm">{error.message}</div>

  const raw = hw.rawJson ?? {}
  const cfg = raw.config ?? raw.deviceConfig ?? {}
  const inverterCfg = cfg.inverterConfig ?? null
  const meterCfg = cfg.meterConfig ?? null
  const weatherCfg = cfg.weatherConfig ?? null
  const archived = raw.fieldsArchived ?? []
  const isVirtual = hw.isVirtualDevice
  const isSerial = SERIAL_COM_TYPES.includes(hw.portMode) || SERIAL_COM_TYPES.includes(hw.comType)
  const isTcp = hw.portMode === 'Tcp' || hw.comType === 'Tcp'
  const driverSettings = hw.driverSettings ?? {}

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">

      {/* Header */}
      <div>
        <button onClick={() => navigate(`/sites/${siteId}`)} className="text-xs text-zinc-500 hover:text-zinc-300 mb-2 block">
          ← Site {siteId}
        </button>
        <div className="flex items-start gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-semibold text-zinc-100">{hw.name}</h1>
              {hw.flags.map(f => <StatusBadge key={f} label={f} color={FLAG_COLORS[f] ?? 'gray'} />)}
              {isVirtual && <StatusBadge label="Virtual" color="gray" />}
            </div>
            <div className="text-xs font-mono text-zinc-500 mt-0.5">ID: {hw.id}</div>
          </div>
        </div>
      </div>

      {/* Identity */}
      <Section title="Identity">
        <CopyField label="Name" value={hw.name} mono={false} />
        <CopyField label="String ID" value={hw.stringId} />
        <CopyField label="Serial Number" value={hw.serialNumber} />
        <DataField label="Function Code" value={hw.functionCode} mono />
        <DataField label="Device Type" value={hw.deviceType} />
        <DataField label="Timezone" value={hw.timezone} />
      </Section>

      {/* Network / comms — smart section */}
      {isVirtual ? (
        <div className="space-y-3">
          <div className="text-xs font-medium text-zinc-500 uppercase tracking-wider border-b border-zinc-800 pb-1">Network / Communications</div>
          <VirtualBanner />
          {/* Component inverters if present */}
          {Array.isArray(inverterCfg) && inverterCfg.length > 1 && (
            <div className="space-y-2 pt-1">
              <div className="text-xs text-zinc-500">Component Inverters ({inverterCfg.length})</div>
              <InverterTable inverters={inverterCfg} />
            </div>
          )}
        </div>
      ) : (
        <Section title="Network / Communications">
          {/* comType badge */}
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-zinc-500 uppercase tracking-wider">Protocol</span>
            <ComTypeBadge comType={hw.comType} portMode={hw.portMode} />
          </div>

          {/* IP / host — most important for TCP */}
          <CopyField label="IP Address" value={hw.ipAddress} highlight />
          <CopyField label="Modbus ID" value={hw.modbusAddress !== '0' ? hw.modbusAddress : null} />
          <CopyField
            label={isTcp ? 'TCP Port' : isSerial ? 'Serial Port' : 'Port'}
            value={hw.portNumber || hw.port || null}
          />
          {isSerial && <DataField label="Baud Rate" value={hw.baudRate} mono />}

          {/* Gateway link */}
          {hw.gatewayId && (
            <div className="flex flex-col gap-0.5">
              <span className="text-xs text-zinc-500 uppercase tracking-wider">Gateway</span>
              <Link
                to={`/gateways/${encodeURIComponent(hw.gatewayId)}`}
                className="text-sm font-mono text-blue-400 hover:text-blue-300 truncate"
                onClick={e => e.stopPropagation()}
              >
                {hw.gateway?.name && hw.gateway.name !== hw.gatewayId
                  ? `${hw.gateway.name} (${hw.gatewayId})`
                  : hw.gatewayId}
              </Link>
            </div>
          )}

          {/* Driver */}
          {hw.driverName && <DataField label="Driver" value={hw.driverName} />}
        </Section>
      )}

      {/* Driver settings — shown for all non-virtual devices that have them */}
      {!isVirtual && Object.keys(driverSettings).length > 0 && (
        <Section title="Driver Settings">
          <DriverSettingsTable settings={driverSettings} />
        </Section>
      )}

      {/* Device-type-specific config (single inverter) */}
      {!isVirtual && inverterCfg && !Array.isArray(inverterCfg) && Object.keys(inverterCfg).length > 0 && (
        <Section title="Inverter Config">
          {Object.entries(inverterCfg).map(([k, v]) => <CopyField key={k} label={k} value={v} />)}
        </Section>
      )}
      {meterCfg && Object.keys(meterCfg).length > 0 && (
        <Section title="Meter Config">
          {Object.entries(meterCfg).map(([k, v]) => <CopyField key={k} label={k} value={v} />)}
        </Section>
      )}
      {weatherCfg && Object.keys(weatherCfg).length > 0 && (
        <Section title="Weather Station Config">
          {Object.entries(weatherCfg).map(([k, v]) => <CopyField key={k} label={k} value={v} />)}
        </Section>
      )}

      {/* Archived fields */}
      {archived.length > 0 && (
        <Section title={`Archived Fields (${archived.length})`}>
          <div className="col-span-full flex flex-wrap gap-1.5">
            {archived.map((f, i) => (
              <span key={i} className="font-mono text-xs bg-zinc-800 text-zinc-400 border border-zinc-700 px-2 py-0.5 rounded">
                {typeof f === 'string' ? f : f.fieldName ?? JSON.stringify(f)}
              </span>
            ))}
          </div>
        </Section>
      )}

      <JsonViewer data={hw.rawJson} />
    </div>
  )
}
