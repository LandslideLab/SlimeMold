import type { MetricFamilies, SimResult, Spec } from '../types'
import { hierarchySpec } from '../defaults'

export function metricsFixture(): MetricFamilies {
  return {
    performance: {
      throughput: 85.5,
      success_rate: 0.72,
      mean_flow_time: 3.2,
      value_delivered: 150.25,
      sla_breach_rate: 0.02,
      n_completed: 120,
      n_failed: 30,
    },
    coordination: {
      messages: 420,
      messages_per_task: 2.8,
      mean_waiting_turns: 1.4,
      escalations: 12,
      approval_messages: 60,
      consult_messages: 8,
      supervision_load: 0.42,
    },
    quality: {
      error_rate: 0.05,
      uncaught_risk: 0.012,
      deadlock_resolutions: 3,
      deadlock_failures: 0,
    },
    decision: {
      mean_decision_latency: 2.1,
      autonomy_share: 0.63,
    },
    knowledge: {
      retention_rate: 0.5,
      revalidation_rate: 0.9,
      learning_curve: {
        windows: [0, 30, 60, 90],
        success_by_window: [0.6, 0.7, 0.56, 0.69],
      },
      knowledge_volume: 8,
    },
    resilience: {
      events: [],
      note: 'no turnover events occurred',
      mean_drop: 0,
      mean_recovery_turns: 0,
    },
  }
}

export function resultFixture(overrides: Partial<SimResult> = {}): SimResult {
  const spec: Spec = hierarchySpec()
  const roleList = spec.organization.roles
  return {
    config: { turns: 120, seed: 42, max_attempts: 2, knowledge_weight: 0.4, supervision_enabled: true },
    organization: {
      name: 'cs-hierarchy',
      roles: Object.fromEntries(
        roleList.map((r) => [
          r.id,
          { id: r.id, name: r.name, capabilities: r.capabilities, autonomy: r.autonomy, responsibilities: [], mandate: [] },
        ]),
      ),
      reporting: { agent1: 'lead', agent2: 'lead', lead: null },
      shape: 'hierarchy',
      max_depth: 2,
      max_span: 2,
      avg_span: 2,
    },
    institution: {},
    taskflow: {},
    turnover: {},
    knowledge: {},
    tasks: [
      {
        id: 'T1-1',
        task_type: 't1',
        capability: 't1',
        complexity: 0.4,
        risk: 0.2,
        cost: 1,
        value: 1,
        arrival_turn: 1,
        required_turns: 2,
        is_novel: false,
        anomaly: null,
        state: 'completed',
        owner_role_id: 'agent1',
        completed_turn: 3,
        flow_time: 2,
        escalation_count: 0,
      },
    ],
    events: [
      {
        turn: 1,
        kind: 'msg:assign',
        subject: 'T1-1',
        actor: 'org',
        message: 'org -> agent1 [assign]',
        data: { sender: 'org', receiver: 'agent1' },
      },
    ],
    messages: [
      { id: 'M1', kind: 'assign', sender: 'org', receiver: 'agent1', turn: 1, task_id: 'T1-1', payload: {} },
    ],
    timeline: [
      { turn: 1, active_tasks: 1, waiting: 0, executing: 1 },
      { turn: 2, active_tasks: 1, waiting: 0, executing: 1 },
    ],
    turnover_events: [],
    metrics: metricsFixture(),
    engine_version: '0.1.0',
    spec,
    ...overrides,
  }
}
