import type {
  CompareResult,
  HealthStatus,
  ScanResult,
  SimResult,
  Spec,
} from './types'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init)
  const text = await res.text()
  let body: unknown = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = null
  }
  if (!res.ok) {
    const msg =
      body && typeof body === 'object' && 'error' in body
        ? String((body as { error: unknown }).error)
        : `HTTP ${res.status}`
    throw new Error(msg)
  }
  return body as T
}

export function isEngineReachable(): Promise<boolean> {
  return request<HealthStatus>('/health')
    .then((h) => h.status === 'ok')
    .catch(() => false)
}

export async function fetchHealth(): Promise<HealthStatus> {
  return request<HealthStatus>('/health')
}

export async function fetchExampleSpec(): Promise<Spec> {
  return request<Spec>('/spec/example')
}

export async function simulate(
  spec: Spec,
  seed?: number,
  turns?: number,
): Promise<SimResult> {
  return request<SimResult>('/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ spec, seed, turns }),
  })
}

export interface CompareRequest {
  specA: Spec
  specB: Spec
  metric: string
  reps: number
  seed: number
  test: string
  turns?: number
}

export async function compare(req: CompareRequest): Promise<CompareResult> {
  return request<CompareResult>('/experiment', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      mode: 'compare',
      spec_a: req.specA,
      spec_b: req.specB,
      metric: req.metric,
      reps: req.reps,
      seed: req.seed,
      test: req.test,
      turns: req.turns,
    }),
  })
}

export interface ScanRequest {
  spec: Spec
  parameter: string
  values: Array<number | string | null>
  metric: string
  seed: number
  turns?: number
  reps: number
}

export async function scan(req: ScanRequest): Promise<ScanResult> {
  return request<ScanResult>('/experiment', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      mode: 'scan',
      spec: req.spec,
      parameter: req.parameter,
      values: req.values,
      metric: req.metric,
      seed: req.seed,
      turns: req.turns,
      reps: req.reps,
    }),
  })
}

export interface ReportRequest {
  spec: Spec
  seed: number
  note: string
}

export async function oddReport(req: ReportRequest): Promise<{ odd: string }> {
  return request<{ odd: string }>('/report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ spec: req.spec, seed: req.seed, note: req.note }),
  })
}
