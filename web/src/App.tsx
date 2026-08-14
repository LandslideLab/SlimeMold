import { useEffect, useState } from 'react'
import type { HealthStatus, SimResult, Spec } from './types'
import { isEngineReachable, fetchHealth, fetchExampleSpec } from './api'
import { hierarchySpec } from './defaults'
import { Designer } from './components/Designer'
import { Simulate } from './components/Simulate'
import { ComparePanel } from './components/ComparePanel'
import { ScanPanel } from './components/ScanPanel'
import { ExportPanel } from './components/ExportPanel'
import { orgStats } from './lib/org'

type Tab = 'design' | 'simulate' | 'compare' | 'scan' | 'export'

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'design', label: 'Design' },
  { id: 'simulate', label: 'Run' },
  { id: 'compare', label: 'Compare' },
  { id: 'scan', label: 'Scan' },
  { id: 'export', label: 'Export' },
]

function App() {
  const [tab, setTab] = useState<Tab>('design')
  const [spec, setSpec] = useState<Spec | null>(null)
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [engineState, setEngineState] = useState<'checking' | 'ok' | 'offline'>('checking')
  const [lastResult, setLastResult] = useState<SimResult | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const reachable = await isEngineReachable()
      if (cancelled) return
      setEngineState(reachable ? 'ok' : 'offline')
      if (reachable) {
        try {
          const h = await fetchHealth()
          setHealth(h)
        } catch {
          /* keep offline marker */
        }
      }
      try {
        const ex = await fetchExampleSpec()
        if (!cancelled) setSpec(ex)
      } catch {
        if (!cancelled) setSpec(hierarchySpec())
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  function onSimulated(r: SimResult) {
    setLastResult(r)
  }

  const stats = spec ? orgStats(spec.organization.roles, spec.organization.reporting) : null

  return (
    <div className="app">
      <header className="masthead">
        <div className="masthead-inner">
          <a className="brand" href="#" onClick={(e) => { e.preventDefault(); setTab('design') }}>
            <span className="brand-mark">S</span>
            <span>
              <span className="brand-name">SlimeMold</span>
              <span className="brand-sub">Org Design Sim Testbed</span>
            </span>
          </a>
          <nav className="tabbar" aria-label="Main">
            {TABS.map((t) => (
              <button key={t.id} className="tab" data-active={tab === t.id} onClick={() => setTab(t.id)}>
                {t.label}
              </button>
            ))}
          </nav>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 16 }}>
            <span
              className="status-dot"
              data-state={engineState === 'ok' ? 'ok' : engineState === 'offline' ? 'err' : 'run'}
              title={engineState === 'ok' ? `engine ${health?.engine_version ?? ''} online` : 'engine offline'}
            />
            <span className="label-mono">
              {engineState === 'ok'
                ? `engine v${health?.engine_version ?? '?'}`
                : engineState === 'offline'
                  ? 'engine offline'
                  : 'connecting…'}
            </span>
          </div>
        </div>
      </header>

      <main className="app-main">
        {tab === 'design' && (
          <section className="container" style={{ paddingTop: 24, paddingBottom: 48 }}>
            <div className="hero" style={{ border: 'none', padding: '0 0 18px' }}>
              <div className="hero-rule" />
              <h1 style={{ marginBottom: 8 }}>Organization designer</h1>
              <p className="lede" style={{ marginBottom: 12 }}>
                Drag roles to build the reporting topology, then tune the institutional rules —
                delegation, supervision budget, approval gates — and the environment. The DSL spec
                is what the engine runs, byte-for-byte.
              </p>
              <div className="meta-strip">
                <div className="meta-cell">
                  <div className="label-mono">Roles</div>
                  <div className="meta-value">{stats?.nRoles ?? 0}</div>
                </div>
                <div className="meta-cell">
                  <div className="label-mono">Depth</div>
                  <div className="meta-value">{stats?.maxDepth ?? 0}</div>
                </div>
                <div className="meta-cell">
                  <div className="label-mono">Span</div>
                  <div className="meta-value">{stats?.maxSpan ?? 0}</div>
                </div>
                <div className="meta-cell">
                  <div className="label-mono">Shape</div>
                  <div className="meta-value" style={{ fontSize: 13 }}>{stats?.shape ?? '—'}</div>
                </div>
                <div className="meta-cell">
                  <div className="label-mono">Spec</div>
                  <div className="meta-value" style={{ fontSize: 13 }}>{spec?.name ?? '—'}</div>
                </div>
              </div>
            </div>
            {engineState === 'offline' && (
              <div className="error-box">
                Engine offline — the web testbed talks to the Python engine over the headless JSON
                protocol. Start it with:{'\n'}$ cd web && npm run dev:engine
              </div>
            )}
            {spec && <Designer spec={spec} onChange={setSpec} />}
          </section>
        )}

        {tab === 'simulate' && spec && (
          <SimulateView key={JSON.stringify(spec.organization.name)} spec={spec} onDone={onSimulated} />
        )}

        {tab === 'compare' && spec && (
          <section className="container" style={{ paddingTop: 24, paddingBottom: 48 }}>
            <ComparePanel currentSpec={spec} />
          </section>
        )}

        {tab === 'scan' && spec && (
          <section className="container" style={{ paddingTop: 24, paddingBottom: 48 }}>
            <ScanPanel currentSpec={spec} />
          </section>
        )}

        {tab === 'export' && spec && (
          <section className="container" style={{ paddingTop: 24, paddingBottom: 48 }}>
            <ExportPanel spec={spec} result={lastResult} />
          </section>
        )}
      </main>

      <footer className="footer">
        <div className="footer-inner">
          <div className="label-mono">
            SlimeMold · human + AI organization design · ABM vertical for organization management
          </div>
          <div className="label-mono">
            deterministic · seeded · {engineState === 'ok' ? 'engine connected' : 'standalone'}
          </div>
        </div>
      </footer>
    </div>
  )
}

function SimulateView({ spec, onDone }: { spec: Spec; onDone: (r: SimResult) => void }) {
  const [result, setResult] = useState<SimResult | null>(null)
  return (
    <section className="container" style={{ paddingBottom: 48 }}>
      <Simulate
        spec={spec}
        onDone={(r) => {
          setResult(r)
          onDone(r)
        }}
      />
      {result && (
        <div style={{ marginTop: 12 }}>
          <div className="label-mono">
            Result cached for Export. Run again to refresh.
          </div>
        </div>
      )}
    </section>
  )
}

export default App
