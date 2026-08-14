import type { Spec } from './types'

export function hierarchySpec(budget: number | null = 3): Spec {
  return {
    name: 'customer-service-hierarchy',
    sim: { turns: 120, seed: 42 },
    organization: {
      name: 'cs-hierarchy',
      roles: [
        { id: 'lead', name: 'Team Lead', capabilities: ['review'], autonomy: 'approver' },
        { id: 'agent1', name: 'CS Agent 1', capabilities: ['t1', 't2'], autonomy: 'collaborator' },
        { id: 'agent2', name: 'CS Agent 2', capabilities: ['t1', 't3'], autonomy: 'collaborator' },
      ],
      reporting: { agent1: 'lead', agent2: 'lead' },
    },
    institution: {
      delegation_strategy: 'controlled',
      supervision_budget: { lead: budget },
      approval_gates: [{ kind: 'risk', threshold: 0.7 }],
      escalation_timeout: 6,
      max_wait_turns: 15,
    },
    taskflow: {
      arrival_rate: 1.4,
      task_types: ['t1', 't2', 't3'],
      complexity_mu: 0.45,
      risk_mu: 0.35,
      dynamism: 0.01,
      anomaly_probability: 0.03,
      novelty_probability: 0.05,
    },
    knowledge: {
      sharing_probability: 0.7,
      half_life: 50,
      revalidation_probability: 0.12,
    },
    turnover: { per_turn_probability: 0.002 },
  }
}

export function flatSpec(): Spec {
  const spec = hierarchySpec()
  spec.name = 'customer-service-flat'
  if (spec.organization) {
    spec.organization.name = 'cs-flat'
    spec.organization.roles = [
      { id: 'agent1', name: 'CS Agent 1', capabilities: ['t1', 't2'], autonomy: 'approver' },
      { id: 'agent2', name: 'CS Agent 2', capabilities: ['t1', 't3'], autonomy: 'approver' },
      { id: 'agent3', name: 'CS Agent 3', capabilities: ['t2', 't3'], autonomy: 'approver' },
    ]
    spec.organization.reporting = { agent1: null, agent2: null, agent3: null }
  }
  spec.institution = {
    delegation_strategy: 'full',
    supervision_budget: {},
    approval_gates: [],
    escalation_timeout: 6,
    max_wait_turns: 15,
  }
  return spec
}

export type PresetId = 'hierarchy' | 'flat'

export const PRESETS: Array<{ id: PresetId; label: string; make: () => Spec }> = [
  { id: 'hierarchy', label: 'Hierarchy — 3 roles / 2 levels', make: hierarchySpec },
  { id: 'flat', label: 'Flat — 3 roles / 1 level', make: flatSpec },
]

export function emptySpec(): Spec {
  return {
    name: 'custom-organization',
    sim: { turns: 120, seed: 42 },
    organization: {
      name: 'custom-org',
      roles: [{ id: 'r1', name: 'Role 1', capabilities: ['t1'], autonomy: 'collaborator' }],
      reporting: { r1: null },
    },
    institution: {
      delegation_strategy: 'controlled',
      supervision_budget: {},
      approval_gates: [],
      escalation_timeout: 6,
      max_wait_turns: 15,
    },
    taskflow: {
      arrival_rate: 1.0,
      task_types: ['t1'],
      complexity_mu: 0.4,
      risk_mu: 0.3,
      dynamism: 0.0,
      anomaly_probability: 0.02,
      novelty_probability: 0.05,
    },
    knowledge: { sharing_probability: 0.7, half_life: 40, revalidation_probability: 0.1 },
    turnover: { per_turn_probability: 0.0 },
  }
}
