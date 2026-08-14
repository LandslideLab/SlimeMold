import type { ReactNode } from 'react'
import type { MetricFamilies } from '../types'
import { LineChart } from './Chart'
import { fmt, pct } from '../lib/format'

export function MetricDashboard({ metrics }: { metrics: MetricFamilies }) {
  const p = metrics.performance
  const c = metrics.coordination
  const q = metrics.quality
  const d = metrics.decision
  const k = metrics.knowledge
  const r = metrics.resilience

  const lc = k.learning_curve ?? { windows: [], success_by_window: [] }
  const lcPoints = lc.windows.map((w, i) => ({
    x: w,
    label: String(w),
    value: lc.success_by_window[i] ?? 0,
  }))

  return (
    <div>
      <div className="grid-4">
        <MetricCard label="Performance" value={fmt(p.throughput, 1)} unit="tasks/turn">
          <MetricRow k="Success rate" v={pct(p.success_rate)} />
          <MetricRow k="Mean flow time" v={fmt(p.mean_flow_time, 1)} />
          <MetricRow k="SLA breach" v={pct(p.sla_breach_rate)} />
        </MetricCard>
        <MetricCard label="Coordination cost" value={fmt(c.messages_per_task, 2)} unit="msgs/task">
          <MetricRow k="Total messages" v={String(c.messages)} />
          <MetricRow k="Mean waiting" v={fmt(c.mean_waiting_turns, 2)} />
          <MetricRow k="Escalations" v={String(c.escalations)} />
        </MetricCard>
        <MetricCard label="Quality &amp; safety" value={pct(q.error_rate)}>
          <MetricRow k="Uncaught risk" v={pct(q.uncaught_risk)} />
          <MetricRow k="Deadlock resolves" v={String(q.deadlock_resolutions)} />
          <MetricRow k="Deadlock failures" v={String(q.deadlock_failures)} />
        </MetricCard>
        <MetricCard label="Decision" value={fmt(d.autonomy_share * 100, 0)} unit="% autonomy">
          <MetricRow k="Decision latency" v={fmt(d.mean_decision_latency, 2)} />
        </MetricCard>
      </div>

      <div style={{ height: 16 }} />

      <div className="grid-2">
        <div className="panel">
          <div className="panel-head">
            <span className="label">Knowledge — organizational learning</span>
          </div>
          <div className="panel-body">
            <div className="metric-row">
              <span>Retention rate</span>
              <span>{pct(k.retention_rate)}</span>
            </div>
            <div className="metric-row">
              <span>Revalidation rate</span>
              <span>{pct(k.revalidation_rate)}</span>
            </div>
            <div className="metric-row">
              <span>Knowledge volume</span>
              <span>{String(k.knowledge_volume)}</span>
            </div>
            <div style={{ height: 10 }} />
            <span className="label">Learning curve — success by window</span>
            <LineChart points={lcPoints} height={150} yLabel="success" />
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <span className="label">Resilience — turnover impact</span>
          </div>
          <div className="panel-body">
            <div className="metric-row">
              <span>Turnover events</span>
              <span>{String(r.events.length)}</span>
            </div>
            <div className="metric-row">
              <span>Mean performance drop</span>
              <span>{pct(r.mean_drop)}</span>
            </div>
            <div className="metric-row">
              <span>Mean recovery turns</span>
              <span>{fmt(r.mean_recovery_turns, 1)}</span>
            </div>
            <div style={{ height: 10 }} />
            <span className="label">Note</span>
            <p style={{ fontSize: 12, color: '#4a4a4a', marginTop: 4 }}>{r.note}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function MetricCard({
  label,
  value,
  unit,
  children,
}: {
  label: string
  value: string
  unit?: string
  children?: ReactNode
}) {
  return (
    <div className="metric-card">
      <div className="metric-card-head">{label}</div>
      <div className="metric-card-body">
        <div>
          <span className="metric-big">{value}</span>
          {unit && <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#7d7d76', marginLeft: 6 }}>{unit}</span>}
        </div>
        {children}
      </div>
    </div>
  )
}

function MetricRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="metric-row">
      <span>{k}</span>
      <span style={{ color: '#141414' }}>{v}</span>
    </div>
  )
}
