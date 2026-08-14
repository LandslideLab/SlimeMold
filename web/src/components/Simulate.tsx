import { useState } from 'react'
import type { SimResult, Spec } from '../types'
import { simulate } from '../api'
import { RunResults } from './RunResults'
import { orgStats } from '../lib/org'

export function Simulate({ spec, onDone }: { spec: Spec; onDone?: (r: SimResult) => void }) {
  const [seed, setSeed] = useState<number>(spec.sim?.seed ?? 42)
  const [turns, setTurns] = useState<number>(spec.sim?.turns ?? 120)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SimResult | null>(null)

  const stats = orgStats(spec.organization.roles, spec.organization.reporting)

  async function run() {
    setRunning(true)
    setError(null)
    try {
      const res = await simulate(spec, seed, turns)
      setResult(res)
      onDone?.(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <div className="hero" style={{ padding: '28px 0 24px' }}>
        <div className="container">
          <div className="section-head" style={{ marginBottom: 10 }}>
            <div>
              <span className="label">Run</span>
              <div className="section-title">Simulate a single organization design</div>
            </div>
          </div>
          <p style={{ maxWidth: '80ch', color: '#4a4a4a', marginBottom: 14 }}>
            Runs the current design ({spec.organization.name}) for <strong>{turns}</strong> turns with
            seed <strong>{seed}</strong>. {stats.nRoles} roles · depth {stats.maxDepth} · span{' '}
            {stats.maxSpan}. Each run is fully deterministic and logged.
          </p>
          <div className="inline-field" style={{ gap: 18 }}>
            <div className="inline-field">
              <label htmlFor="seed">seed</label>
              <input id="seed" type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} style={{ width: 110 }} />
            </div>
            <div className="inline-field">
              <label htmlFor="turns">turns</label>
              <input id="turns" type="number" min={1} value={turns} onChange={(e) => setTurns(Math.max(1, Number(e.target.value)))} style={{ width: 110 }} />
            </div>
            <button className="btn btn-red" disabled={running} onClick={run}>
              {running ? <span className="spinner" style={{ borderTopColor: '#fff' }} /> : '▶ Run'}
            </button>
            {running && <span className="label-mono">engine running…</span>}
          </div>
        </div>
      </div>

      <div className="container">
        {error && <div className="error-box">{error}</div>}
        {!error && running && (
          <div className="error-box" style={{ borderLeftColor: 'var(--swiss-red)', background: 'var(--swiss-gray-50)' }}>
            Running deterministic simulation (seed {seed}, {turns} turns)…
          </div>
        )}
        {result && <RunResults result={result} />}
        {!result && !running && !error && (
          <div className="empty" style={{ marginTop: 40 }}>
            No run yet — press “Run” to execute the current design with the engine.
          </div>
        )}
      </div>
    </div>
  )
}
