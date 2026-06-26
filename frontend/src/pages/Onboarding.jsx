import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

const STEPS = ['Welcome', 'Credentials', 'Test', 'Save']

function StepDots({ current }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {STEPS.map((label, i) => (
        <div key={i} className="flex items-center gap-2">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-colors ${
              i < current
                ? 'bg-emerald-600 text-white'
                : i === current
                ? 'bg-blue-500 text-white'
                : 'bg-zinc-700 text-zinc-400'
            }`}
          >
            {i < current ? '✓' : i + 1}
          </div>
          <span className={`text-xs ${i === current ? 'text-zinc-200' : 'text-zinc-500'}`}>
            {label}
          </span>
          {i < STEPS.length - 1 && <div className="w-6 h-px bg-zinc-700" />}
        </div>
      ))}
    </div>
  )
}

function WelcomeStep({ onNext }) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-bold text-zinc-100 mb-2">r3think Extraction Tool</h2>
        <p className="text-zinc-400 leading-relaxed">
          This tool connects to the AlsoEnergy PowerTrack API to extract site and device
          configuration data for N3uron migration. Everything runs locally — no data leaves
          your machine.
        </p>
      </div>
      <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 space-y-2">
        <p className="text-sm font-medium text-zinc-300">What you'll need</p>
        <ul className="text-sm text-zinc-400 space-y-1 list-disc list-inside">
          <li>Your AlsoEnergy PowerTrack username</li>
          <li>Your AlsoEnergy PowerTrack password</li>
        </ul>
      </div>
      <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 space-y-2">
        <p className="text-sm font-medium text-zinc-300">Privacy</p>
        <p className="text-sm text-zinc-400">
          Credentials are stored in your OS secure keychain (macOS Keychain / Windows Credential
          Manager). They are never written to disk in plain text or sent anywhere.
        </p>
      </div>
      <button
        onClick={onNext}
        className="mt-2 self-start px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors"
      >
        Get started
      </button>
    </div>
  )
}

function CredentialsStep({ username, password, onChange, onNext, onBack }) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-bold text-zinc-100 mb-1">Enter credentials</h2>
        <p className="text-zinc-400 text-sm">
          Your AlsoEnergy PowerTrack login. We'll test them on the next step before saving.
        </p>
      </div>
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-1">Username</label>
          <input
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => onChange('username', e.target.value)}
            placeholder="username"
            className="w-full rounded-lg border border-zinc-600 bg-zinc-800 px-3 py-2 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-1">Password</label>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => onChange('password', e.target.value)}
            placeholder="••••••••"
            className="w-full rounded-lg border border-zinc-600 bg-zinc-800 px-3 py-2 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>
      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="px-4 py-2 rounded-lg border border-zinc-600 text-zinc-300 hover:text-zinc-100 hover:border-zinc-400 transition-colors text-sm"
        >
          Back
        </button>
        <button
          onClick={onNext}
          disabled={!username || !password}
          className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
        >
          Test connection
        </button>
      </div>
    </div>
  )
}

function TestStep({ username, password, onNext, onBack }) {
  const [status, setStatus] = useState('idle') // idle | testing | ok | fail
  const [error, setError] = useState('')

  async function runTest() {
    setStatus('testing')
    setError('')
    try {
      const res = await api.post('/auth/test', { username, password })
      if (res.ok) {
        setStatus('ok')
      } else {
        setStatus('fail')
        setError(res.error || 'Authentication failed')
      }
    } catch (e) {
      setStatus('fail')
      setError(e.message || 'Network error')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-bold text-zinc-100 mb-1">Test connection</h2>
        <p className="text-zinc-400 text-sm">
          Verify your credentials against the AlsoEnergy API before saving.
        </p>
      </div>

      {status === 'idle' && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 text-sm text-zinc-400">
          Click <span className="text-zinc-200 font-medium">Run test</span> to check your credentials.
          Nothing will be saved yet.
        </div>
      )}

      {status === 'testing' && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 flex items-center gap-3">
          <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-zinc-300">Connecting to AlsoEnergy API…</span>
        </div>
      )}

      {status === 'ok' && (
        <div className="rounded-lg border border-emerald-700 bg-emerald-900/20 p-4 flex items-center gap-3">
          <span className="text-emerald-400 text-lg">✓</span>
          <div>
            <p className="text-sm font-medium text-emerald-300">Connection successful</p>
            <p className="text-xs text-emerald-500 mt-0.5">Ready to save credentials to your keychain.</p>
          </div>
        </div>
      )}

      {status === 'fail' && (
        <div className="rounded-lg border border-red-700 bg-red-900/20 p-4">
          <p className="text-sm font-medium text-red-300">Connection failed</p>
          <p className="text-xs text-red-400 mt-1 font-mono">{error}</p>
          <p className="text-xs text-zinc-400 mt-2">Check your credentials and try again.</p>
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="px-4 py-2 rounded-lg border border-zinc-600 text-zinc-300 hover:text-zinc-100 hover:border-zinc-400 transition-colors text-sm"
        >
          Back
        </button>
        {status !== 'ok' ? (
          <button
            onClick={runTest}
            disabled={status === 'testing'}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-lg font-medium transition-colors"
          >
            {status === 'testing' ? 'Testing…' : status === 'fail' ? 'Retry' : 'Run test'}
          </button>
        ) : (
          <button
            onClick={onNext}
            className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-medium transition-colors"
          >
            Save & continue
          </button>
        )}
      </div>
    </div>
  )
}

function SaveStep({ username, password, onDone }) {
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')

  async function save() {
    setStatus('saving')
    try {
      await api.post('/credentials', { username, password })
      setStatus('ok')
      setTimeout(onDone, 1200)
    } catch (e) {
      setStatus('fail')
      setError(e.message || 'Failed to save credentials')
    }
  }

  // Auto-save on mount
  useEffect(() => { save() }, [])

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-bold text-zinc-100 mb-1">Saving credentials</h2>
        <p className="text-zinc-400 text-sm">
          Storing your credentials in the OS secure keychain.
        </p>
      </div>

      {(status === 'idle' || status === 'saving') && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 flex items-center gap-3">
          <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-zinc-300">Saving to keychain…</span>
        </div>
      )}

      {status === 'ok' && (
        <div className="rounded-lg border border-emerald-700 bg-emerald-900/20 p-4 flex items-center gap-3">
          <span className="text-emerald-400 text-lg">✓</span>
          <div>
            <p className="text-sm font-medium text-emerald-300">Credentials saved</p>
            <p className="text-xs text-emerald-500 mt-0.5">Launching dashboard…</p>
          </div>
        </div>
      )}

      {status === 'fail' && (
        <div className="rounded-lg border border-red-700 bg-red-900/20 p-4">
          <p className="text-sm font-medium text-red-300">Save failed</p>
          <p className="text-xs text-red-400 mt-1 font-mono">{error}</p>
        </div>
      )}
    </div>
  )
}

export function Onboarding({ onComplete }) {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  function handleChange(field, value) {
    if (field === 'username') setUsername(value)
    else setPassword(value)
  }

  function handleDone() {
    if (onComplete) onComplete()
    else navigate('/', { replace: true })
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-6">
      <div className="w-full max-w-lg">
        <StepDots current={step} />
        <div className="rounded-xl border border-zinc-700 bg-zinc-900 p-8 shadow-2xl">
          {step === 0 && <WelcomeStep onNext={() => setStep(1)} />}
          {step === 1 && (
            <CredentialsStep
              username={username}
              password={password}
              onChange={handleChange}
              onNext={() => setStep(2)}
              onBack={() => setStep(0)}
            />
          )}
          {step === 2 && (
            <TestStep
              username={username}
              password={password}
              onNext={() => setStep(3)}
              onBack={() => setStep(1)}
            />
          )}
          {step === 3 && (
            <SaveStep
              username={username}
              password={password}
              onDone={handleDone}
            />
          )}
        </div>
      </div>
    </div>
  )
}
