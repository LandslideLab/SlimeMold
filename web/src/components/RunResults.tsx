import { useMemo, useState } from 'react'
import type { SimResult } from '../types'
import { TimelinePlayer } from './TimelinePlayer'
import { MetricDashboard } from './Dashboard'
import { LineChart } from './Chart'
import { fmt, shortId } from '../lib/format'
import { download, specToYaml } from '../lib/org'
import { oddReport } from '../api'

export function RunResults({ result }: { result: SimResult }) {
  const [showEvents, setShowEvents] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportMsg, setExportMsg] = useState<string | null>(null)

  const timelinePoints = result.timeline.map((t) => ({ x: t.turn, label: String(t.turn), value: t.active_tasks }))
  const waitingPoints = result.timeline.map((t) => ({ x: t.turn, value: t.waiting }))
  const executingPoints = result.timeline.map((t) => ({ x: t.turn, value: t.executing }))

  const activeMessage = useMemo(() => {
    const active = result.tasks.filter((t) => t.state === 'running' || t.state === 'waiting')
    return active.length
  }, [result])

  const sortedTasks = useMemo(() => {
    return [...result.tasks].sort((a, b) => a.arrival_turn - b.arrival_turn)
  }, [result])

  async function exportReproduction() {
    setExporting(true)
    setExportMsg(null)
    try {
      const rep = await oddReport({ spec: result.spec, seed: result.config.seed, note: 'Generated from the SlimeMold web testbed.' })
      download('ODD-report.txt', rep.odd, 'text/plain')
      setExportMsg('ODD protocol report downloaded.')
    } catch (e) {
      setExportMsg(`ODD report failed: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <div className="statusbar">
        <span className="status-dot" data-state="ok" />
        <span>
          Run complete — <strong>{result.organization.name}</strong> · seed {result.config.seed} ·
          {result.config.turns} turns · engine {result.engine_version}
        </span>
        <span style={{ marginLeft: 'auto' }} className="label-mono">
          {result.config.turns} turns · {result.metrics.performance.n_completed} done ·{' '}
          {result.metrics.performance.n_failed} failed · {activeMessage} active
        </span>
        <span style={{ display: 'flex', gap: 8, marginLeft: 12 }}>
          <button className="btn btn-sm" onClick={() => download(`result-${result.organization.name}.json`, JSON.stringify(result, null, 2))}>
            ↓ result.json
          </button>
          <button className="btn btn-sm btn-ghost" onClick={() => download(`spec-${result.organization.name}.yaml`, specToYaml(result.spec), 'text/yaml')}>
            ↓ spec.yaml
          </button>
          <button className="btn btn-sm btn-ghost" disabled={exporting} onClick={exportReproduction}>
            {exporting ? <span className="spinner" /> : '↓ ODD report'}
          </button>
        </span>
      </div>
      {exportMsg && (
        <div className="error-box" style={{ borderLeftColor: 'var(--swiss-blue)', background: 'var(--swiss-gray-50)' }}>
          {exportMsg}
        </div>
      )}

      <div className="viz-grid">
        <TimelinePlayer result={result} />
        <div>
          <div className="panel" style={{ marginBottom: 16 }}>
            <div className="panel-head">
              <span className="label">Queue — active / waiting / executing</span>
            </div>
            <div className="panel-body">
              <LineChart points={timelinePoints} height={150} yLabel="active" color="#141414" />
              <div className="legend">
                <span className="legend-item"><span className="legend-swatch black" /> active</span>
              </div>
              <div style={{ height: 12 }} />
              <LineChart points={executingPoints} height={100} yLabel="executing" color="#0f5bd0" />
              <div className="legend">
                <span className="legend-item"><span className="legend-swatch blue" /> executing</span>
              </div>
              <div style={{ height: 12 }} />
              <LineChart points={waitingPoints} height={100} yLabel="waiting" color="#7d7d76" />
              <div className="legend">
                <span className="legend-item"><span className="legend-line" /> waiting</span>
              </div>
            </div>
          </div>
          <div className="panel">
            <div className="panel-head">
              <span className="label">Organization</span>
            </div>
            <div className="panel-body">
              <div className="kv"><span>Shape</span><span>{result.organization.shape}</span></div>
              <div className="kv"><span>Roles</span><span>{Object.keys(result.organization.roles).length}</span></div>
              <div className="kv"><span>Max depth</span><span>{result.organization.max_depth}</span></div>
              <div className="kv"><span>Max span</span><span>{result.organization.max_span}</span></div>
              <div className="kv"><span>Avg span</span><span>{fmt(result.organization.avg_span, 1)}</span></div>
            </div>
          </div>
        </div>
      </div>

      <div style={{ height: 24 }} />
      <div className="section-head">
        <div>
          <span className="label">Constructs</span>
          <div className="section-title">Metrics dashboard</div>
        </div>
      </div>
      <MetricDashboard metrics={result.metrics} />

      <div style={{ height: 24 }} />
      <div className="section-head">
        <div>
          <span className="label">Observation</span>
          <div className="section-title">Tasks &amp; event log</div>
        </div>
        <button className="btn btn-sm btn-ghost" onClick={() => setShowEvents((v) => !v)}>
          {showEvents ? 'Hide events' : 'Show events'}
        </button>
      </div>

      <div className="table-wrap panel">
        <table>
          <thead>
            <tr>
              <th>Task</th>
              <th>Type</th>
              <th>Arrival</th>
              <th>Done</th>
              <th className="num">Complexity</th>
              <th className="num">Risk</th>
              <th className="num">Flow</th>
              <th className="num">Esc</th>
              <th>Owner</th>
              <th>State</th>
            </tr>
          </thead>
          <tbody>
            {sortedTasks.slice(0, 60).map((t) => (
              <tr key={t.id}>
                <td>{t.id}</td>
                <td>{t.task_type}</td>
                <td>{t.arrival_turn}</td>
                <td>{t.completed_turn ?? '—'}</td>
                <td className="num">{t.complexity.toFixed(2)}</td>
                <td className="num">{t.risk.toFixed(2)}</td>
                <td className="num">{fmt(t.flow_time, 1)}</td>
                <td className="num">{t.escalation_count}</td>
                <td>{shortId(t.owner_role_id)}</td>
                <td>{t.state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="label-mono" style={{ marginTop: 6 }}>
        Showing {Math.min(60, sortedTasks.length)} of {sortedTasks.length} tasks
      </p>

      {showEvents && (
        <div className="table-wrap panel" style={{ marginTop: 16, maxHeight: 380, overflowY: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Turn</th>
                <th>Kind</th>
                <th>Actor</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {result.events.slice(-400).map((e, i) => (
                <tr key={i}>
                  <td>{e.turn}</td>
                  <td>{e.kind}</td>
                  <td>{shortId(e.actor)}</td>
                  <td style={{ whiteSpace: 'normal', minWidth: 320 }}>{e.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
