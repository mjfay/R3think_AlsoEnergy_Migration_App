// UI labels use "Extraction" — internal code calls these "migrations" for legacy compatibility
import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import r3thinkLogo from './assets/r3think-logo.png'
import { Dashboard } from './pages/Dashboard'
import { SitesList } from './pages/SitesList'
import { SiteDetail } from './pages/SiteDetail'
import { DeviceDetail } from './pages/DeviceDetail'
import { GatewayDetail } from './pages/GatewayDetail'
import { Onboarding } from './pages/Onboarding'
import { MigrationsList } from './pages/MigrationsList'
import { NewMigrationJob } from './pages/NewMigrationJob'
import { MigrationJobDetail } from './pages/MigrationJobDetail'
import { Discovery } from './pages/Discovery'
import { Settings } from './pages/Settings'
import { api } from './lib/api'
import './index.css'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } })

const navCls = ({ isActive }) =>
  `px-3 py-1.5 text-sm rounded transition-colors ${isActive ? 'bg-zinc-700 text-zinc-100' : 'text-zinc-400 hover:text-zinc-200'}`

function MainApp() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-200">
      <nav className="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-6 py-2 flex items-center gap-2">
          <img src={r3thinkLogo} alt="r3think labs" className="h-6 mr-4 object-contain" />
          <NavLink to="/" end className={navCls}>Dashboard</NavLink>
          <NavLink to="/sites" className={navCls}>Sites</NavLink>
          <NavLink to="/migrations" className={navCls}>Extractions</NavLink>
          <NavLink to="/discovery" className={navCls}>Find TCP</NavLink>
          <div className="ml-auto">
            <NavLink
              to="/settings"
              title="Settings"
              className={({ isActive }) =>
                `flex items-center justify-center w-10 h-10 rounded transition-colors ${isActive ? 'bg-zinc-700 text-zinc-100' : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'}`
              }
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
              </svg>
            </NavLink>
          </div>
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/sites" element={<SitesList />} />
        <Route path="/sites/:siteId" element={<SiteDetail />} />
        <Route path="/sites/:siteId/hardware/:hardwareId" element={<DeviceDetail />} />
        <Route path="/gateways/:gatewayId" element={<GatewayDetail />} />
        <Route path="/migrations" element={<MigrationsList />} />
        <Route path="/migrations/new" element={<NewMigrationJob />} />
        <Route path="/migrations/:jobId" element={<MigrationJobDetail />} />
        <Route path="/discovery" element={<Discovery />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/onboarding" element={<Onboarding />} />
      </Routes>
    </div>
  )
}

function AppGate() {
  // 'loading' | 'onboarding' | 'ready'
  const [state, setState] = useState('loading')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    async function check() {
      // Poll until the backend responds — it takes ~15s to extract in packaged mode
      for (let i = 0; i < 40; i++) {
        if (cancelled) return
        try {
          const res = await api.credentialsStatus()
          if (!cancelled) setState(res.stored ? 'ready' : 'onboarding')
          return
        } catch {
          // Backend not up yet — wait and retry
          await new Promise(r => setTimeout(r, 1000))
          if (!cancelled) setAttempt(i + 1)
        }
      }
      // After 40s give up and show the app anyway (dev mode / backend on PATH)
      if (!cancelled) setState('ready')
    }
    check()
    return () => { cancelled = true }
  }, [])

  if (state === 'loading') {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center gap-4">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-zinc-500">Starting backend{attempt > 3 ? ` (${attempt}s…)` : '…'}</p>
      </div>
    )
  }

  if (state === 'onboarding') {
    return (
      <Routes>
        <Route path="*" element={<Onboarding onComplete={() => setState('ready')} />} />
      </Routes>
    )
  }

  return <MainApp />
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AppGate />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
