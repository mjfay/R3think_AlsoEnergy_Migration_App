import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'

const TOOL_VERSION = '0.1.0'

function Section({ title, children }) {
  return (
    <div className="border border-zinc-700 rounded-xl overflow-hidden">
      <div className="px-5 py-3 border-b border-zinc-700 bg-zinc-800/50">
        <h2 className="text-sm font-semibold text-zinc-300">{title}</h2>
      </div>
      <div className="divide-y divide-zinc-800">{children}</div>
    </div>
  )
}

function Row({ label, description, children }) {
  return (
    <div className="px-5 py-4 flex items-center justify-between gap-6">
      <div className="flex-1">
        <p className="text-sm text-zinc-200">{label}</p>
        {description && <p className="text-xs text-zinc-500 mt-0.5">{description}</p>}
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  )
}

export function Settings() {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: health } = useQuery({ queryKey: ['health'], queryFn: api.health })
  const { data: credStatus } = useQuery({ queryKey: ['credStatus'], queryFn: api.credentialsStatus })
  const { data: stats } = useQuery({ queryKey: ['stats'], queryFn: api.stats })
  const { data: dirInfo } = useQuery({ queryKey: ['dataDir'], queryFn: () => api.get('/admin/data-dir') })

  const [clearConfirm, setClearConfirm] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [clearError, setClearError] = useState('')
  const [histConfirm, setHistConfirm] = useState(false)
  const [clearingHist, setClearingHist] = useState(false)
  const [histError, setHistError] = useState('')

  const username = health?.token?.status === 'valid'
    ? '(authenticated)'
    : credStatus?.stored
    ? '(stored in keychain)'
    : 'Not configured'

  const dataDir = dirInfo?.dataDir || '(loading…)'

  async function handleClearCache() {
    setClearing(true)
    setClearError('')
    try {
      // Clear hardware, gateways but keep sites (they're cheap to re-sync)
      // For now: full wipe by hitting a reset endpoint
      await api.post('/admin/clear-cache', {})
      qc.invalidateQueries()
      setClearConfirm(false)
    } catch (e) {
      setClearError(e.message)
    } finally {
      setClearing(false)
    }
  }

  async function handleClearMigrationHistory() {
    setClearingHist(true)
    setHistError('')
    try {
      await api.post('/admin/clear-migration-history', {})
      qc.invalidateQueries()
      setHistConfirm(false)
    } catch (e) {
      setHistError(e.message)
    } finally {
      setClearingHist(false)
    }
  }

  function handleReenterCredentials() {
    navigate('/onboarding')
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <h1 className="text-xl font-semibold text-zinc-100">Settings</h1>

      {/* Account */}
      <Section title="Account">
        <Row
          label="AlsoEnergy account"
          description={credStatus?.stored ? 'Credentials saved in OS keychain' : 'No credentials stored'}
        >
          <div className="flex items-center gap-3">
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${
              credStatus?.stored ? 'bg-emerald-900/60 text-emerald-300' : 'bg-zinc-700 text-zinc-400'
            }`}>
              {credStatus?.stored ? 'Stored' : 'Not set'}
            </span>
            <button
              onClick={handleReenterCredentials}
              className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
            >
              Re-enter credentials
            </button>
          </div>
        </Row>
        <Row
          label="Token status"
          description="OAuth token is held in memory only — cleared on app restart"
        >
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
            health?.token?.status === 'valid'
              ? 'bg-emerald-900/60 text-emerald-300'
              : 'bg-zinc-700 text-zinc-400'
          }`}>
            {health?.token?.status ?? 'unknown'}
          </span>
        </Row>
      </Section>

      {/* r3think Contact */}
      <Section title="r3think Contact Emails">
        <Row
          label="Recipient addresses"
          description="CSV exports are emailed to these addresses. Edit if they change."
        >
          <div className="text-xs text-zinc-400 text-right">
            <div>robert@r3thinklabs.com</div>
            <div>michael@r3thinklabs.com</div>
          </div>
        </Row>
        <div className="px-5 py-3">
          <p className="text-xs text-zinc-600">
            Contact r3think labs to update these addresses. Customisable address fields coming in a future release.
          </p>
        </div>
      </Section>

      {/* Data */}
      <Section title="Data">
        <Row
          label="Cached data"
          description={stats ? `${stats.totalSites} sites · ${stats.totalDevices} devices · ${stats.totalGateways} gateways` : 'Loading…'}
        >
          {!clearConfirm ? (
            <button
              onClick={() => setClearConfirm(true)}
              className="text-sm text-red-400 hover:text-red-300 transition-colors"
            >
              Clear cache
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-400">Are you sure?</span>
              <button
                onClick={handleClearCache}
                disabled={clearing}
                className="text-xs px-2 py-1 bg-red-700 hover:bg-red-600 text-white rounded transition-colors disabled:opacity-40"
              >
                {clearing ? 'Clearing…' : 'Yes, clear'}
              </button>
              <button
                onClick={() => { setClearConfirm(false); setClearError('') }}
                className="text-xs px-2 py-1 border border-zinc-600 text-zinc-400 rounded hover:text-zinc-200 transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </Row>
        {clearError && (
          <div className="px-5 pb-3">
            <p className="text-xs text-red-400">{clearError}</p>
          </div>
        )}
        <Row
          label="Migration history"
          description="Delete all migration jobs and their generated CSVs from the jobs list. The files on disk are not deleted."
        >
          {!histConfirm ? (
            <button
              onClick={() => setHistConfirm(true)}
              className="text-sm text-red-400 hover:text-red-300 transition-colors"
            >
              Clear history
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-400">Are you sure?</span>
              <button
                onClick={handleClearMigrationHistory}
                disabled={clearingHist}
                className="text-xs px-2 py-1 bg-red-700 hover:bg-red-600 text-white rounded transition-colors disabled:opacity-40"
              >
                {clearingHist ? 'Clearing…' : 'Yes, clear'}
              </button>
              <button
                onClick={() => { setHistConfirm(false); setHistError('') }}
                className="text-xs px-2 py-1 border border-zinc-600 text-zinc-400 rounded hover:text-zinc-200 transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </Row>
        {histError && (
          <div className="px-5 pb-3">
            <p className="text-xs text-red-400">{histError}</p>
          </div>
        )}
        <Row
          label="Data folder"
          description={dataDir}
        />
      </Section>

      {/* About */}
      <Section title="About">
        <Row label="App version">
          <span className="text-sm text-zinc-400">{TOOL_VERSION}</span>
        </Row>
        <Row label="Built by">
          <span className="text-sm text-zinc-400">r3think labs</span>
        </Row>
      </Section>
    </div>
  )
}
