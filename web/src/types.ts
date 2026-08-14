export type Autonomy =
  | 'operator'
  | 'collaborator'
  | 'consultant'
  | 'approver'
  | 'observer'

export const AUTONOMIES: Autonomy[] = [
  'operator',
  'collaborator',
  'consultant',
  'approver',
  'observer',
]

export const AUTONOMY_LABEL: Record<Autonomy, string> = {
  operator: 'Operator',
  collaborator: 'Collaborator',
  consultant: 'Consultant',
  approver: 'Approver',
  observer: 'Observer',
}

export interface OrgRoleSpec {
  id: string
  name: string
  capabilities: string[]
  responsibilities?: string[]
  autonomy: Autonomy
  mandate?: string[]
}

export interface ApprovalGateSpec {
  kind: string
  threshold: number
}

export interface Spec {
  name?: string
  sim?: {
    turns?: number
    seed?: number
    max_attempts?: number
    knowledge_weight?: number
    supervision_enabled?: boolean
  }
  organization: {
    name?: string
    roles: OrgRoleSpec[]
    reporting: Record<string, string | null>
  }
  institution?: {
    delegation_strategy?: string
    supervision_budget?: Record<string, number | null>
    default_supervision_budget?: number | null
    approval_gates?: ApprovalGateSpec[]
    approval_turn_cost?: number
    escalation_timeout?: number
    max_wait_turns?: number
    risk_acceptance?: number
  }
  taskflow?: {
    arrival_rate?: number
    task_types?: string[]
    capability_by_type?: Record<string, string>
    complexity_mu?: number
    risk_mu?: number
    cost_mu?: number
    dynamism?: number
    anomaly_probability?: number
    novelty_probability?: number
    shift_every?: number
    load_multiplier?: number
  }
  knowledge?: {
    sharing_probability?: number
    half_life?: number
    revalidation_probability?: number
    max_items_per_member?: number
    noise?: number
  }
  turnover?: {
    per_turn_probability?: number
    schedule?: Record<string, unknown>
    replace_experience?: number
    onboarding_turns?: number
    knowledge_loss_fraction?: number
  }
  agents?: Array<Record<string, unknown>>
}

export interface SimConfig {
  turns: number
  seed: number
  max_attempts: number
  knowledge_weight: number
  supervision_enabled: boolean
}

export interface MetricFamilies {
  performance: {
    throughput: number
    success_rate: number
    mean_flow_time: number
    value_delivered: number
    sla_breach_rate: number
    n_completed: number
    n_failed: number
  }
  coordination: {
    messages: number
    messages_per_task: number
    mean_waiting_turns: number
    escalations: number
    approval_messages: number
    consult_messages: number
    supervision_load: number
  }
  quality: {
    error_rate: number
    uncaught_risk: number
    deadlock_resolutions: number
    deadlock_failures: number
  }
  decision: {
    mean_decision_latency: number
    autonomy_share: number
  }
  knowledge: {
    retention_rate: number
    revalidation_rate: number
    learning_curve: { windows: number[]; success_by_window: number[] }
    knowledge_volume: number
  }
  resilience: {
    events: unknown[]
    note: string
    mean_drop: number
    mean_recovery_turns: number
  }
}

export interface TaskResult {
  id: string
  task_type: string
  capability: string
  complexity: number
  risk: number
  cost: number
  value: number
  arrival_turn: number
  required_turns: number
  is_novel: boolean
  anomaly: unknown
  state: string
  owner_role_id: string | null
  completed_turn: number | null
  flow_time: number
  escalation_count: number
  parent_id?: string | null
  subtasks?: unknown
}

export interface TimelinePoint {
  turn: number
  active_tasks: number
  waiting: number
  executing: number
}

export interface BusMessage {
  id: string
  kind: string
  sender: string
  receiver: string
  turn: number
  task_id: string | null
  payload: Record<string, unknown>
}

export interface EventRecord {
  turn: number
  kind: string
  subject: string | null
  actor: string
  message: string
  data: Record<string, unknown>
}

export interface OrgDerived {
  name: string
  roles: Record<string, OrgRoleSpec & { responsibilities: string[]; mandate: string[] }>
  reporting: Record<string, string | null>
  shape: string
  max_depth: number
  max_span: number
  avg_span: number
}

export interface SimResult {
  config: SimConfig
  organization: OrgDerived
  institution: Record<string, unknown>
  taskflow: Record<string, unknown>
  turnover: Record<string, unknown>
  knowledge: Record<string, unknown>
  tasks: TaskResult[]
  events: EventRecord[]
  messages: BusMessage[]
  timeline: TimelinePoint[]
  turnover_events: unknown[]
  metrics: MetricFamilies
  engine_version: string
  spec: Spec
}

export interface CompareStatistics {
  mean_a: number
  sd_a: number
  mean_b: number
  sd_b: number
  cohens_d: number
  test: string
  u: number
  z: number
  p: number
  significant: boolean
}

export interface CompareResult {
  mode: 'compare'
  metric: string
  reps: number
  values_a: number[]
  values_b: number[]
  statistics: CompareStatistics
  seeds: number[]
  spec_a: Spec
  spec_b: Spec
}

export interface ScanResult {
  mode: 'scan'
  parameter: string
  path: string
  values: Array<number | string>
  metric: string
  metric_values: number[]
  seeds: number[]
  spec_template: Spec
}

export interface HealthStatus {
  status: string
  engine_version: string
}

export interface ExperimentParams {
  metric: string
  label: string
  higherIsBetter: boolean
}

export const METRICS: ExperimentParams[] = [
  { metric: 'throughput', label: 'Throughput', higherIsBetter: true },
  { metric: 'success_rate', label: 'Success rate', higherIsBetter: true },
  { metric: 'mean_flow_time', label: 'Mean flow time', higherIsBetter: false },
  { metric: 'messages_per_task', label: 'Messages / task', higherIsBetter: false },
  { metric: 'mean_waiting_turns', label: 'Mean waiting turns', higherIsBetter: false },
  { metric: 'escalations', label: 'Escalations', higherIsBetter: false },
  { metric: 'error_rate', label: 'Error rate', higherIsBetter: false },
  { metric: 'uncaught_risk', label: 'Uncaught risk', higherIsBetter: false },
  { metric: 'autonomy_share', label: 'Autonomy share', higherIsBetter: true },
  { metric: 'mean_decision_latency', label: 'Decision latency', higherIsBetter: false },
  { metric: 'retention_rate', label: 'Knowledge retention', higherIsBetter: true },
  { metric: 'revalidation_rate', label: 'Revalidation rate', higherIsBetter: true },
]
