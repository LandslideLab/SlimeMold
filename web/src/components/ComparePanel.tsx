import { useState } from 'react'
import type { CompareResult, Spec } from '../types'
import { METRICS } from '../types'
import { compare } from '../api'
import { hierarchySpec, flatSpec } from '../defaults'
import { PairedBarChart } from './Chart'
import { fmt } from '../lib/format'

type SlotKind = 'current' | 'hierarchy' | 'flat' | 'custom'

interface SpecSlot {
  kind: SlotKind
  customJson: string
}

function resolveSpec(slot: SpecSlot, current: Spec): Spec {
  if (slot.kind === 'current') return current
  if (slot.kind === 'hierarchy') return hierarchySpec()
  if (slot.kind === 'flat') return flatSpec()
  return JSON.parse(slot.customJson) as Spec
}

export function ComparePanel({ currentSpec }: { currentSpec: Spec }) {
  const [a, setA] = useState<SpecSlot>({ kind: 'current', customJson: '' })
  const [b, setB] = useState<SpecSlot>({ kind: 'hierarchy', customJson: '' })
  const [metric, setMetric] = useState('throughput')
  const [reps, setReps] = useState(8)
  const [seed, setSeed] = useState(42)
  const [test, setTest] = useState('mann_whitney')
  const [turns, setTurns] = useState<number>(120)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CompareResult | null>(null)

  function labelOf(slot: SpecSlot): string {
    if (slot.kind === 'current') return currentSpec.name ?? 'current'
    if (slot.kind === 'hierarchy') return 'hierarchy'
    if (slot.kind === 'flat') return 'flat'
    return 'custom'
  }

  async function run() {
    setRunning(true)
    setError(null)
    try {
      const res = await compare({
        specA: resolveSpec(a, currentSpec),
        specB: resolveSpec(b, currentSpec),
        metric,
        reps,
        seed,
        test,
        turns: turns > 0 ? turns : undefined,
      })
      setResult(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  const repLabels = Array.from({ length: reps }, (_, i) => String(i + 1))

  return (
    <div>
      <div className="hero" style={{ padding: '28px 0 24px' }}>
        <div className="container">
          <div className="section-head" style={{ marginBottom: 10 }}>
            <div>
              <span className="label">Experiment — compare</span>
              <div className="section-title">Design A vs Design B, paired &amp; significance-tested</div>
            </div>
          </div>
          <p style={{ maxWidth: '80ch', color: '#4a4a4a', marginBottom: 14 }}>
            Runs both designs for <strong>{reps}</strong> seeded repetitions each (identical seeds,
            paired), extracts a single metric per run and reports means, effect size and a
            significance test. This answers “is A better than B?”.
          </p>
          <div className="inline-field" style={{ gap: 18, flexWrap: 'wrap' }}>
            <div className="inline-field">
              <label htmlFor="cmp-metric">metric</label>
              <select id="cmp-metric" value={metric} onChange={(e) => setMetric(e.target.value)} style={{ width: 190 }}>
                {METRICS.map((m) => (
                  <option key={m.metric} value={m.metric}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="inline-field">
              <label htmlFor="cmp-reps">reps</label>
              <input id="cmp-reps" type="number" min={1} max={64} value={reps} onChange={(e) => setReps(Math.max(1, Math.min(64, Number(e.target.value))))} style={{ width: 70 }} />
            </div>
            <div className="inline-field">
              <label htmlFor="cmp-seed">seed</label>
              <input id="cmp-seed" type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} style={{ width: 90 }} />
            </div>
            <div className="inline-field">
              <label htmlFor="cmp-test">test</label>
              <select id="cmp-test" value={test} onChange={(e) => setTest(e.target.value)} style={{ width: 150 }}>
                <option value="mann_whitney">Mann–Whitney U</option>
                <option value="t">Welch t</option>
                <option value="auto">auto</option>
              </select>
            </div>
            <div className="inline-field">
              <label htmlFor="cmp-turns">turns</label>
              <input id="cmp-turns" type="number" min={1} value={turns} onChange={(e) => setTurns(Number(e.target.value))} style={{ width: 80 }} />
            </div>
            <button className="btn btn-red" disabled={running} onClick={run}>
              {running ? <span className="spinner" style={{ borderTopColor: '#fff' }} /> : '▶ Compare'}
            </button>
          </div>
        </div>
      </div>

      <div className="container">
        <div className="grid-2" style={{ marginBottom: 20 }}>
          <SlotEditor title="Design A" slot={a} onChange={setA} currentSpec={currentSpec} accent="black" />
          <SlotEditor title="Design B" slot={b} onChange={setB} currentSpec={currentSpec} accent="red" />
        </div>

        {error && <div className="error-box">{error}</div>}
        {!error && running && (
          <div className="error-box" style={{ borderLeftColor: 'var(--swiss-red)', background: 'var(--swiss-gray-50)' }}>
            Running {reps}×2 seeded comparisons…
          </div>
        )}

        {result && (
          <>
            <div className="section-head">
              <div>
                <span className="label">Result</span>
                <div className="section-title">
                  {labelOf(a)} vs {labelOf(b)} — {result.metric}
                </div>
              </div>
              <span className="chip chip-red" style={{ fontSize: 12 }}>
                {result.statistics.significant ? 'SIGNIFICANT' : 'NOT SIGNIFICANT'}
              </span>
            </div>

            <div className="grid-2">
              <div className="panel">
                <div className="panel-head">
                  <span className="label">Per-repetition values ({result.reps} reps)</span>
                </div>
                <div className="panel-body">
                  <PairedBarChart labels={repLabels} valuesA={result.values_a} valuesB={result.values_b} />
                  <div className="legend">
                    <span className="legend-item"><span className="legend-swatch black" /> A — {labelOf(a)}</span>
                    <span className="legend-item"><span className="legend-swatch red" /> B — {labelOf(b)}</span>
                  </div>
                </div>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <span className="label">Statistics</span>
                </div>
                <div className="panel-body">
                  <div className="kv"><span>Mean A</span><span>{fmt(result.statistics.mean_a, 3)}</span></div>
                  <div className="kv"><span>SD A</span><span>{fmt(result.statistics.sd_a, 3)}</span></div>
                  <div className="kv"><span>Mean B</span><span>{fmt(result.statistics.mean_b, 3)}</span></div>
                  <div className="kv"><span>SD B</span><span>{fmt(result.statistics.sd_b, 3)}</span></div>
                  <div className="kv"><span>Cohen's d</span><span>{fmt(result.statistics.cohens_d, 3)}</span></div>
                  <div className="kv"><span>Test</span><span>{result.statistics.test}</span></div>
                  <div className="kv"><span>U</span><span>{fmt(result.statistics.u, 2)}</span></div>
                  <div className="kv"><span>z</span><span>{fmt(result.statistics.z, 3)}</span></div>
                  <div className="kv"><span>p-value</span><span>{result.statistics.p.toFixed(4)}</span></div>
                  <div className="kv">
                    <span>Verdict</span>
                    <span style={{ fontWeight: 700, color: result.statistics.significant ? 'var(--swiss-red)' : '#4a4a4a' }}>
                      {result.statistics.significant ? 'significant' : 'not significant'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <div style={{ height: 14 }} />
            <div className="panel">
              <div className="panel-head">
                <span className="label">Derived seeds (identical for A &amp; B)</span>
              </div>
              <div className="panel-body">
                <p className="label-mono" style={{ wordBreak: 'break-all' }}>{result.seeds.join(', ')}</p>
              </div>
            </div>
          </>
        )}
        {!result && !error && !running && (
          <div className="empty" style={{ marginTop: 20 }}>No comparison yet — configure both designs and press “Compare”.</div>
        )}
      </div>
    </div>
  )
}

function SlotEditor({
  title,
  slot,
  onChange,
  currentSpec,
  accent,
}: {
  title: string
  slot: SpecSlot
  onChange: (s: SpecSlot) => void
  currentSpec: Spec
  accent: 'black' | 'red'
}) {
  const [parseError, setParseError] = useState<string | null>(null)
  function tryParse() {
    try {
      resolveSpec(slot, currentSpec)
      setParseError(null)
    } catch (e) {
      setParseError(e instanceof Error ? e.message : String(e))
    }
  }
  return (
    <div className="panel">
      <div className="panel-head">
        <span className="label" style={{ borderBottom: `3px solid ${accent === 'red' ? 'var(--swiss-red)' : 'var(--swiss-black)'}` }}>
          {title}
        </span>
        <select
          value={slot.kind}
          onChange={(e) => onChange({ ...slot, kind: e.target.value as SlotKind })}
          style={{ width: 180 }}
          aria-label={`${title} source`}
        >
          <option value="current">current design ({currentSpec.name ?? '?'})</option>
          <option value="hierarchy">hierarchy preset</option>
          <option value="flat">flat preset</option>
          <option value="custom">paste JSON</option>
        </select>
      </div>
      <div className="panel-body">
        {slot.kind === 'custom' ? (
          <>
            <textarea
              rows={10}
              value={slot.customJson}
              onChange={(e) => onChange({ ...slot, customJson: e.target.value })}
              placeholder={'{\n  "name": "my-design",\n  "organization": { "roles": [...] },\n  ...\n}'}
              style={{ fontFamily: 'monospace', fontSize: 11 }}
            />
            <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
              <button className="btn btn-sm btn-ghost" onClick={tryParse}>Validate</button>
              <span className="label-mono">{resolveSpecSafe(slot, currentSpec)}</span>
              {parseError && <span className="label-mono" style={{ color: 'var(--swiss-red)' }}>{parseError}</span>}
            </div>
          </>
        ) : (
          <div className="label-mono" style={{ whiteSpace: 'pre-wrap', fontSize: 11 }}>
            {describeSpec(resolveSpec(slot, currentSpec))}
          </div>
        )}
      </div>
    </div>
  )
}

function resolveSpecSafe(slot: SpecSlot, current: Spec): string {
  try {
    const s = resolveSpec(slot, current)
    return `${s.organization.roles.length} roles · ${s.sim?.turns ?? 100} turns`
  } catch (e) {
    return e instanceof Error ? e.message : 'invalid'
  }
}

function describeSpec(spec: Spec): string {
  const org = spec.organization
  const edges = Object.values(org.reporting).filter(Boolean).length
  return [
    `name: ${spec.name ?? '?'}`,
    `roles: ${org.roles.length} (${org.roles.map((r) => r.id).join(', ')})`,
    `reporting edges: ${edges}`,
    `turns: ${spec.sim?.turns ?? 100} · seed: ${spec.sim?.seed ?? 42}`,
    `arrival: ${spec.taskflow?.arrival_rate ?? 1} · dynamism: ${spec.taskflow?.dynamism ?? 0}`,
    `delegation: ${spec.institution?.delegation_strategy ?? 'controlled'}`,
  ].join('\n')
}
