import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

// Step indicators
function Steps({ current }) {
  const labels = ['Name', 'Select Sites', 'Confirm']
  return (
    <div className="flex items-center gap-2 mb-8">
      {labels.map((label, i) => (
        <div key={i} className="flex items-center gap-2">
          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-colors ${
            i < current ? 'bg-emerald-600 text-white' : i === current ? 'bg-blue-500 text-white' : 'bg-zinc-700 text-zinc-400'
          }`}>
            {i < current ? '✓' : i + 1}
          </div>
          <span className={`text-xs ${i === current ? 'text-zinc-200' : 'text-zinc-500'}`}>{label}</span>
          {i < labels.length - 1 && <div className="w-8 h-px bg-zinc-700" />}
        </div>
      ))}
    </div>
  )
}

// Step A: Name the job
function NameStep({ name, onChange, onNext }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-zinc-100 mb-1">Name this export</h2>
        <p className="text-sm text-zinc-400">Used as the CSV filename prefix.</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-zinc-300 mb-1">Export name</label>
        <input
          type="text"
          value={name}
          onChange={(e) => onChange(e.target.value)}
          placeholder="e.g. Southwest Region Q3 2026"
          className="w-full rounded-lg border border-zinc-600 bg-zinc-800 px-3 py-2 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          autoFocus
          onKeyDown={(e) => e.key === 'Enter' && name.trim() && onNext()}
        />
      </div>
      <button
        onClick={onNext}
        disabled={!name.trim()}
        className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
      >
        Next: Select sites
      </button>
    </div>
  )
}

// Step B: Select sites
function SiteSelectStep({ selectedIds, onToggle, onSelectAll, onDeselectAll, onNext, onBack }) {
  const [search, setSearch] = useState('')
  const { data: sites = [], isLoading } = useQuery({
    queryKey: ['sites'],
    queryFn: api.sites,
  })

  const filtered = useMemo(() => {
    if (!search.trim()) return sites
    const q = search.toLowerCase()
    return sites.filter(s =>
      s.siteName.toLowerCase().includes(q) ||
      String(s.siteId).includes(q) ||
      (s.city || '').toLowerCase().includes(q) ||
      (s.state || '').toLowerCase().includes(q)
    )
  }, [sites, search])

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-zinc-100 mb-1">Select sites</h2>
        <p className="text-sm text-zinc-400">Choose which sites to include in this export.</p>
      </div>

      <div className="flex items-center gap-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search sites…"
          className="flex-1 rounded-lg border border-zinc-600 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button onClick={onSelectAll} className="text-xs text-blue-400 hover:text-blue-300 transition-colors whitespace-nowrap">
          Select all
        </button>
        <button onClick={onDeselectAll} className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors whitespace-nowrap">
          Deselect all
        </button>
      </div>

      <div className="text-xs text-zinc-500">
        {selectedIds.size} of {sites.length} sites selected
      </div>

      <div className="border border-zinc-700 rounded-lg overflow-hidden max-h-96 overflow-y-auto">
        {isLoading && (
          <div className="p-4 text-sm text-zinc-500 text-center">Loading sites…</div>
        )}
        {!isLoading && filtered.length === 0 && (
          <div className="p-4 text-sm text-zinc-500 text-center">No sites match your search.</div>
        )}
        {filtered.map((site, i) => (
          <label
            key={site.siteId}
            className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-zinc-800/60 transition-colors ${
              i < filtered.length - 1 ? 'border-b border-zinc-800' : ''
            }`}
          >
            <input
              type="checkbox"
              checked={selectedIds.has(site.siteId)}
              onChange={() => onToggle(site.siteId)}
              className="w-4 h-4 rounded accent-blue-500"
            />
            <span className="flex-1 text-sm text-zinc-200">{site.siteName}</span>
            <span className="text-xs text-zinc-500">#{site.siteId}</span>
            {site.deviceCount > 0 && (
              <span className="text-xs text-zinc-600">{site.deviceCount} devices</span>
            )}
          </label>
        ))}
      </div>

      <div className="flex gap-3">
        <button onClick={onBack} className="px-4 py-2 rounded-lg border border-zinc-600 text-zinc-300 hover:text-zinc-100 hover:border-zinc-400 transition-colors text-sm">
          Back
        </button>
        <button
          onClick={onNext}
          disabled={selectedIds.size === 0}
          className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
        >
          Next: Review
        </button>
      </div>
    </div>
  )
}

function Toggle({ checked, onToggle }) {
  return (
    <button
      onClick={onToggle}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${checked ? 'bg-blue-600' : 'bg-zinc-600'}`}
    >
      <span className={`inline-block h-4 w-4 rounded-full bg-white transform transition-transform ${checked ? 'translate-x-6' : 'translate-x-1'}`} />
    </button>
  )
}

// Step C: Confirm and run
function ConfirmStep({ name, selectedIds, includeVirtual, onToggleVirtual, includeDataDevices, onToggleDataDevices, onBack, onCreate, creating }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-zinc-100 mb-1">Confirm and run</h2>
        <p className="text-sm text-zinc-400">Review before starting the export.</p>
      </div>

      <div className="border border-zinc-700 rounded-lg divide-y divide-zinc-700">
        <div className="px-4 py-3 flex justify-between">
          <span className="text-sm text-zinc-400">Export name</span>
          <span className="text-sm text-zinc-200 font-medium">{name}</span>
        </div>
        <div className="px-4 py-3 flex justify-between">
          <span className="text-sm text-zinc-400">Sites selected</span>
          <span className="text-sm text-zinc-200">{selectedIds.size}</span>
        </div>
        <div className="px-4 py-3 flex justify-between items-center">
          <div>
            <span className="text-sm text-zinc-400">Include virtual devices</span>
            <p className="text-xs text-zinc-600 mt-0.5">Virtual devices have no Modbus address — rows will be present but channel fields empty.</p>
          </div>
          <Toggle checked={includeVirtual} onToggle={onToggleVirtual} />
        </div>
        <div className="px-4 py-3 flex justify-between items-center">
          <div>
            <span className="text-sm text-zinc-400">Include data/utility devices</span>
            <p className="text-xs text-zinc-600 mt-0.5">Devices with function codes DA, CE, RD, GW — cell modems, gateways, reference data. Usually not Modbus migration targets.</p>
          </div>
          <Toggle checked={includeDataDevices} onToggle={onToggleDataDevices} />
        </div>
      </div>

      <div className="rounded-lg border border-amber-700/50 bg-amber-900/10 p-4 text-sm text-amber-300">
        This will pull hardware data for all {selectedIds.size} selected sites from AlsoEnergy and generate a CSV. This may take a few minutes.
      </div>

      <div className="flex gap-3">
        <button onClick={onBack} className="px-4 py-2 rounded-lg border border-zinc-600 text-zinc-300 hover:text-zinc-100 hover:border-zinc-400 transition-colors text-sm">
          Back
        </button>
        <button
          onClick={onCreate}
          disabled={creating}
          className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white rounded-lg font-medium transition-colors"
        >
          {creating ? 'Starting…' : 'Run Export'}
        </button>
      </div>
    </div>
  )
}

export function NewMigrationJob() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [includeVirtual, setIncludeVirtual] = useState(true)
  const [includeDataDevices, setIncludeDataDevices] = useState(true)
  const [creating, setCreating] = useState(false)

  const { data: allSites = [] } = useQuery({ queryKey: ['sites'], queryFn: api.sites })

  function toggleSite(id) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function handleCreate() {
    setCreating(true)
    try {
      const job = await api.post('/jobs', {
        name,
        site_ids: [...selectedIds],
        include_virtual: includeVirtual,
        include_data_devices: includeDataDevices,
      })
      navigate(`/migrations/${job.id}`)
    } catch (e) {
      alert(`Failed to create job: ${e.message}`)
      setCreating(false)
    }
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <button onClick={() => navigate('/migrations')} className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors">
          ← Back to exports
        </button>
      </div>
      <Steps current={step} />
      <div className="border border-zinc-700 rounded-xl bg-zinc-900 p-8">
        {step === 0 && (
          <NameStep name={name} onChange={setName} onNext={() => setStep(1)} />
        )}
        {step === 1 && (
          <SiteSelectStep
            selectedIds={selectedIds}
            onToggle={toggleSite}
            onSelectAll={() => setSelectedIds(new Set(allSites.map(s => s.siteId)))}
            onDeselectAll={() => setSelectedIds(new Set())}
            onNext={() => setStep(2)}
            onBack={() => setStep(0)}
          />
        )}
        {step === 2 && (
          <ConfirmStep
            name={name}
            selectedIds={selectedIds}
            includeVirtual={includeVirtual}
            onToggleVirtual={() => setIncludeVirtual(v => !v)}
            includeDataDevices={includeDataDevices}
            onToggleDataDevices={() => setIncludeDataDevices(v => !v)}
            onBack={() => setStep(1)}
            onCreate={handleCreate}
            creating={creating}
          />
        )}
      </div>
    </div>
  )
}
