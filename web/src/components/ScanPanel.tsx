import { useState } from 'react'
import type { ScanResult, Spec } from '../types'
import { METRICS } from '../types'
import { scan } from '../api'
import { LineChart } from './Chart'
import { fmt } from '../lib/format'

interface ScanPreset {
  label: string
  param: string
  values: Array<number | string | null>
}

const PRESETS: ScanPreset[] = [
  { label: 'Supervision budget (lead)', param: 'institution.supervision_budget.lead', values: [0, 1, 2, 3, 5, null] },
  { label: 'Arrival rate', param: 'taskflow.arrival_rate', values: [0.5, 0.8, 1.0, 1.2, 1.5, 2.0] },
  { label: 'Task complexity μ', param: 'taskflow.complexity_mu', values: [0.2, 0.3, 0.45, 0.6, 0.8] },
  { label: 'Turnover rate', param: 'turnover.per_turn_probability', values: [0, 0.001, 0.002, 0.005, 0.01] },
  { label: 'Knowledge half-life', param: 'knowledge.half_life', values: [10, 25, 50, 100, 200] },
  { label: 'Escalation timeout', param: 'institution.escalation_timeout', values: [2, 4, 6, 10, 15] },
  { label: 'Anomaly probability', param: 'taskflow.anomaly_probability', values: [0, 0.01, 0.03, 0.06, 0.1] },
  { label: 'Sharing probability', param: 'knowledge.sharing_probability', values: [0, 0.3, 0.5, 0.7, 0.9, 1.0] },
]

function parseValues(raw: string): Array<number | string | null> {
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      if (/^null$/i.test(s) || s === 'none') return null
      const n = Number(s)
      return Number.isFinite(n) ? n : s
    })
}

function formatValue(v: number | string | null): string {
  if (v === null) return '∞ (none)'
  return typeof v === 'number' ? fmt(v, v % 1 ? 2 : 0) : v
}

export function ScanPanel({ currentSpec }: { currentSpec: Spec }) {
  const [presetIdx, setPresetIdx] = useState(0)
  const [param, setParam] = useState(PRESETS[0].param)
  const [valuesRaw, setValuesRaw] = useState(PRESETS[0].values.map((v) => (v === null ? 'none' : String(v))).join(', '))
  const [metric, setMetric] = useState('throughput')
  const [seed, setSeed] = useState(42)
  const [reps, setReps] = useState(2)
  const [turns, setTurns] = useState<number>(120)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ScanResult | null>(null)

  function selectPreset(i: number) {
    const p = PRESETS[i]
    setPresetIdx(i)
    setParam(p.param)
    setValuesRaw(p.values.map((v) => (v === null ? 'none' : String(v))).join(', '))
  }

  async function run() {
    setRunning(true)
    setError(null)
    try {
      const res = await scan({
        spec: currentSpec,
        parameter: param,
        values: parseValues(valuesRaw),
        metric,
        seed,
        turns: turns > 0 ? turns : undefined,
        reps,
      })
      setResult(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  const chartPoints = result
    ? result.values.map((v, i) => ({
        x: typeof v === 'number' ? v : i,
        label: formatValue(v),
        value: result.metric_values[i] ?? 0,
      }))
    : []

  return (
    <div>
      <div className="hero" style={{ padding: '28px 0 24px' }}>
        <div className="container">
          <div className="section-head" style={{ marginBottom: 10 }}>
            <div>
              <span className="label">Experiment — scan</span>
              <div className="section-title">Parameter sensitivity sweep</div>
            </div>
          </div>
          <p style={{ maxWidth: '80ch', color: '#4a4a4a', marginBottom: 14 }}>
            Sweeps a single design knob across a range of values while holding everything else fixed.
            This answers “how does the metric respond to the knob?” — e.g. span-of-control,
            supervision budget, turnover rate.
          </p>
          <div className="inline-field" style={{ gap: 16, flexWrap: 'wrap' }}>
            <div className="inline-field">
              <label htmlFor="scan-preset">knob</label>
              <select
                id="scan-preset"
                value={presetIdx}
                onChange={(e) => selectPreset(Number(e.target.value))}
                style={{ width: 260 }}
              >
                {PRESETS.map((p, i) => (
                  <option key={p.param} value={i}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="inline-field">
              <label htmlFor="scan-param">dot-path</label>
              <input id="scan-param" type="text" value={param} onChange={(e) => setParam(e.target.value)} style={{ width: 260 }} />
            </div>
            <div className="inline-field">
              <label htmlFor="scan-values">values</label>
              <input id="scan-values" type="text" value={valuesRaw} onChange={(e) => setValuesRaw(e.target.value)} style={{ width: 220 }} />
            </div>
          </div>
          <div className="inline-field" style={{ gap: 16, flexWrap: 'wrap', marginTop: 12 }}>
            <div className="inline-field">
              <label htmlFor="scan-metric">metric</label>
              <select id="scan-metric" value={metric} onChange={(e) => setMetric(e.target.value)} style={{ width: 200 }}>
                {METRICS.map((m) => (
                  <option key={m.metric} value={m.metric}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="inline-field">
              <label htmlFor="scan-seed">seed</label>
              <input id="scan-seed" type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} style={{ width: 90 }} />
            </div>
            <div className="inline-field">
              <label htmlFor="scan-reps">reps</label>
              <input id="scan-reps" type="number" min={1} value={reps} onChange={(e) => setReps(Math.max(1, Number(e.target.value)))} style={{ width: 70 }} />
            </div>
            <div className="inline-field">
              <label htmlFor="scan-turns">turns</label>
              <input id="scan-turns" type="number" min={1} value={turns} onChange={(e) => setTurns(Number(e.target.value))} style={{ width: 80 }} />
            </div>
            <button className="btn btn-red" disabled={running} onClick={run}>
              {running ? <span className="spinner" style={{ borderTopColor: '#fff' }} /> : '▶ Scan'}
            </button>
          </div>
        </div>
      </div>

      <div className="container">
        {error && <div className="error-box">{error}</div>}
        {!error && running && (
          <div className="error-box" style={{ borderLeftColor: 'var(--swiss-red)', background: 'var(--swiss-gray-50)' }}>
            Sweeping {parseValues(valuesRaw).length} points × {reps} reps…
          </div>
        )}

        {result && (
          <>
            <div className="section-head">
              <div>
                <span className="label">Sensitivity curve</span>
                <div className="section-title">
                  {result.parameter.split('.').pop()} → {result.metric}
                </div>
              </div>
            </div>
            <div className="panel">
              <div className="panel-body">
                <LineChart points={chartPoints} height={240} yLabel={result.metric} color="#e2001a" />
              </div>
            </div>
            <div style={{ height: 14 }} />
            <div className="table-wrap panel">
              <table>
                <thead>
                  <tr>
                    <th>Parameter value</th>
                    <th className="num">{result.metric}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.values.map((v, i) => (
                    <tr key={i}>
                      <td>{formatValue(v)}</td>
                      <td className="num">{fmt(result.metric_values[i], 4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="label-mono" style={{ marginTop: 6 }}>
              seeds: {result.seeds.join(', ')} — deterministic per point
            </p>
          </>
        )}
        {!result && !error && !running && (
          <div className="empty" style={{ marginTop: 20 }}>No scan yet — pick a knob and press “Scan”.</div>
        )}
      </div>
    </div>
  )
}
