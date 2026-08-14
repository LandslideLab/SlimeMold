import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import {
  isEngineReachable,
  fetchHealth,
  fetchExampleSpec,
  simulate,
  compare,
  scan,
  oddReport,
} from './api'
import { hierarchySpec } from './defaults'

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: status >= 200 && status < 300,
      status,
      text: async () => JSON.stringify(body),
    })),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api client', () => {
  beforeEach(() => {
    mockFetchOnce(200, { status: 'ok', engine_version: '0.1.0' })
  })

  it('isEngineReachable returns true on healthy engine', async () => {
    expect(await isEngineReachable()).toBe(true)
  })

  it('isEngineReachable returns false when fetch throws', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new Error('network down')
    }))
    expect(await isEngineReachable()).toBe(false)
  })

  it('fetchHealth returns health payload', async () => {
    const h = await fetchHealth()
    expect(h.status).toBe('ok')
    expect(h.engine_version).toBe('0.1.0')
  })

  it('fetchExampleSpec returns a spec', async () => {
    mockFetchOnce(200, hierarchySpec())
    const s = await fetchExampleSpec()
    expect(s.organization.roles.length).toBeGreaterThan(0)
  })

  it('simulate posts spec and returns result', async () => {
    mockFetchOnce(200, { config: { seed: 42 } })
    const res = await simulate(hierarchySpec(), 42, 60)
    expect(res.config.seed).toBe(42)
    const call = vi.mocked(fetch).mock.calls[0]
    expect(call[0]).toBe('/api/simulate')
    expect(call[1]?.method).toBe('POST')
  })

  it('compare posts the experiment body', async () => {
    mockFetchOnce(200, { mode: 'compare', statistics: { significant: false } })
    const res = await compare({
      specA: hierarchySpec(),
      specB: hierarchySpec(),
      metric: 'throughput',
      reps: 4,
      seed: 1,
      test: 'mann_whitney',
    })
    expect(res.mode).toBe('compare')
    const call = vi.mocked(fetch).mock.calls[0]
    const parsed = JSON.parse(String(call[1]?.body))
    expect(parsed.mode).toBe('compare')
    expect(parsed.reps).toBe(4)
  })

  it('scan posts the scan body', async () => {
    mockFetchOnce(200, { mode: 'scan', values: [1, 2], metric_values: [3, 4] })
    const res = await scan({
      spec: hierarchySpec(),
      parameter: 'taskflow.arrival_rate',
      values: [1, 2],
      metric: 'throughput',
      seed: 42,
      reps: 1,
    })
    expect(res.metric_values).toEqual([3, 4])
  })

  it('oddReport returns ODD text', async () => {
    mockFetchOnce(200, { odd: 'ODD Protocol Description' })
    const r = await oddReport({ spec: hierarchySpec(), seed: 1, note: '' })
    expect(r.odd).toContain('ODD')
  })

  it('throws a readable error on non-2xx', async () => {
    mockFetchOnce(400, { error: 'spec must define organization' })
    await expect(simulate(hierarchySpec())).rejects.toThrow('spec must define organization')
  })

  it('throws on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new Error('boom')
    }))
    await expect(fetchHealth()).rejects.toThrow('boom')
  })
})
